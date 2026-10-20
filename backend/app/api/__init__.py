"""HTTP API."""

from datetime import date

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.db import database_ok
from app.errors import AppError
from app.schemas import (
    ConversationOut,
    ConversationSummary,
    DocumentOut,
    HealthOut,
    OverviewOut,
    QueryIn,
    QueryOut,
    ReadyOut,
    SettingsOut,
    VersionOut,
    VersionTextOut,
)
from app.seed import seed_demo
from app.services.answering import answer_question
from app.services.embeddings import model_status
from app.services.ingestion import UploadMeta, ingest_replacement, ingest_upload
from app.services.maintenance import assert_demo, delete_document, wipe_business_data
from app.services.present import (
    get_conversation,
    get_document,
    list_conversations,
    list_documents,
    list_versions,
    overview,
    settings_out,
    version_text,
)
from app.services.vectors import qdrant_status

router = APIRouter()


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut()


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    payload, status_code = await run_in_threadpool(build_ready, request.app.state)
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/api/overview", response_model=OverviewOut)
async def get_overview(request: Request) -> OverviewOut:
    return await run_in_threadpool(_overview, request.app.state)


@router.get("/api/settings", response_model=SettingsOut)
async def get_settings_view(request: Request) -> SettingsOut:
    return settings_out(request.app.state)


@router.get("/api/documents", response_model=list[DocumentOut])
async def get_documents(request: Request) -> list[DocumentOut]:
    return await run_in_threadpool(_documents, request.app.state)


@router.post("/api/documents", response_model=DocumentOut, status_code=201)
async def create_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    source_label: str = Form("Synthetic — user upload"),
    effective_date: date = Form(...),
    audience: str = Form("staff"),
) -> DocumentOut:
    settings = request.app.state.settings
    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise AppError("file_too_large", "The file exceeds the upload size cap.", 400)
    document_id = await run_in_threadpool(
        ingest_upload,
        request.app.state,
        file.filename or "upload.txt",
        content,
        UploadMeta(
            title=title,
            category=category,
            source_label=source_label,
            audience=audience,
            effective_date=effective_date,
        ),
    )
    return await run_in_threadpool(_document, request.app.state, document_id)


@router.get("/api/documents/{document_id}", response_model=DocumentOut)
async def read_document(request: Request, document_id: str) -> DocumentOut:
    return await run_in_threadpool(_document, request.app.state, document_id)


@router.delete("/api/documents/{document_id}", status_code=204)
async def remove_document(request: Request, document_id: str) -> None:
    await run_in_threadpool(delete_document, request.app.state, document_id)


@router.get("/api/documents/{document_id}/versions", response_model=list[VersionOut])
async def read_versions(request: Request, document_id: str) -> list[VersionOut]:
    return await run_in_threadpool(_versions, request.app.state, document_id)


@router.post("/api/documents/{document_id}/versions", response_model=DocumentOut, status_code=201)
async def replace_document(
    request: Request,
    document_id: str,
    file: UploadFile = File(...),
    effective_date: date = Form(...),
    title: str | None = Form(None),
) -> DocumentOut:
    settings = request.app.state.settings
    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise AppError("file_too_large", "The file exceeds the upload size cap.", 400)
    await run_in_threadpool(
        ingest_replacement,
        request.app.state,
        document_id,
        file.filename or "upload.txt",
        content,
        effective_date=effective_date,
        title=title,
    )
    return await run_in_threadpool(_document, request.app.state, document_id)


@router.get(
    "/api/documents/{document_id}/versions/{version_id}",
    response_model=VersionTextOut,
)
async def read_version_text(request: Request, document_id: str, version_id: str) -> VersionTextOut:
    return await run_in_threadpool(_version_text, request.app.state, document_id, version_id)


@router.post("/api/query", response_model=QueryOut)
async def query(request: Request, payload: QueryIn) -> QueryOut:
    return await run_in_threadpool(
        answer_question,
        request.app.state,
        question=payload.question,
        conversation_id=payload.conversation_id,
        categories=payload.categories,
        audience=payload.audience,
        retrieval_preference=payload.retrieval_preference,
    )


@router.get("/api/conversations", response_model=list[ConversationSummary])
async def get_conversations(request: Request) -> list[ConversationSummary]:
    return await run_in_threadpool(_conversations, request.app.state)


@router.get("/api/conversations/{conversation_id}", response_model=ConversationOut)
async def read_conversation(request: Request, conversation_id: str) -> ConversationOut:
    return await run_in_threadpool(_conversation, request.app.state, conversation_id)


@router.post("/api/demo/reset", response_model=OverviewOut)
async def reset_demo(request: Request) -> OverviewOut:
    assert_demo(request.app.state)
    payload = await run_in_threadpool(seed_demo, request.app.state)
    return OverviewOut.model_validate(payload)


@router.post("/api/demo/delete-all", response_model=OverviewOut)
async def delete_all(request: Request) -> OverviewOut:
    assert_demo(request.app.state)
    await run_in_threadpool(wipe_business_data, request.app.state)
    return await run_in_threadpool(_overview, request.app.state)


def build_ready(app_state) -> tuple[dict, int]:
    database_ready, database_detail = database_ok(app_state.engine)
    vector_ready, vector_detail = qdrant_status(app_state.qdrant, app_state.settings)
    embedding_ready, embedding_detail = model_status(app_state.settings)
    if not database_ready:
        status = "unavailable"
        code = 503
    elif not vector_ready or not embedding_ready:
        status = "degraded"
        code = 200
    else:
        status = "ok"
        code = 200
    body = ReadyOut(
        status=status,
        checks={
            "database": {"ok": database_ready, "detail": database_detail},
            "qdrant": {"ok": vector_ready, "detail": vector_detail},
            "embeddings": {"ok": embedding_ready, "detail": embedding_detail},
        },
    )
    return body.model_dump(), code


def _session_call(app_state, function, *args):
    session = app_state.session_factory()
    try:
        return function(session, *args)
    finally:
        session.close()


def _overview(app_state):
    session = app_state.session_factory()
    try:
        return overview(session, app_state)
    finally:
        session.close()


def _documents(app_state):
    return _session_call(app_state, list_documents)


def _document(app_state, document_id: str):
    return _session_call(app_state, get_document, document_id)


def _versions(app_state, document_id: str):
    return _session_call(app_state, list_versions, document_id)


def _version_text(app_state, document_id: str, version_id: str):
    return _session_call(app_state, version_text, document_id, version_id)


def _conversations(app_state):
    return _session_call(app_state, list_conversations)


def _conversation(app_state, conversation_id: str):
    return _session_call(app_state, get_conversation, conversation_id)
