"""Application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api import router
from app.config import Settings, enforce_loopback, get_settings
from app.db import ensure_reference_data, make_engine, make_session_factory, run_migrations
from app.errors import AppError
from app.models import Document
from app.seed import seed_demo
from app.services.ingestion import FaultInjected
from app.services.jobs import reap_stale_jobs
from app.services.vectors import close_qdrant, open_qdrant

logger = logging.getLogger("hr_policy_copilot")


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        enforce_loopback(app.state.settings)
        await run_in_threadpool(prepare_runtime, app)
        yield
        close_qdrant(getattr(app.state, "qdrant", None))
        engine = getattr(app.state, "engine", None)
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="HR Policy Copilot",
        version="0.1.0",
        summary="Extractive HR policy answers with hybrid retrieval and exact citations.",
        lifespan=lifespan,
    )
    app.state.settings = configured
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(FaultInjected, _fault_error)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    return app


def prepare_runtime(app: FastAPI) -> None:
    import os
    from pathlib import Path

    settings: Settings = app.state.settings
    if settings.hf_hub_offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.qdrant_path).mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = factory
    session = factory()
    try:
        ensure_reference_data(session)
        reaped = reap_stale_jobs(session, settings.stale_job_seconds)
        if reaped:
            logger.info("reaped %s stale ingestion jobs", reaped)
        document_count = int(
            session.scalar(
                select(func.count()).select_from(Document).where(Document.deleted_at.is_(None))
            )
            or 0
        )
    finally:
        session.close()
    client, error = open_qdrant(settings)
    app.state.qdrant = client
    app.state.qdrant_error = error
    if settings.seed_on_startup and settings.app_env == "demo" and document_count == 0:
        seed_demo(app.state)


async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "code": exc.code},
    )


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "Request validation failed.",
            "code": "validation_error",
            "detail": exc.errors(),
        },
    )


async def _fault_error(_request: Request, _exc: FaultInjected) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "injected fault before vector delete",
            "code": "fault_injected",
        },
    )


app = create_app()
