"""Document ingestion, replacement, and indexing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import bump_corpus_state, ensure_reference_data, utcnow
from app.domain.bm25 import term_counts
from app.domain.chunking import chunk_pages
from app.domain.injection import is_instruction_override
from app.errors import AppError
from app.models import Chunk, ChunkTerm, Document, DocumentVersion, IngestionJob
from app.parsing.hostile import HostileFile
from app.parsing.sandbox import parse_in_subprocess
from app.parsing.uploads import (
    MIME_TYPES,
    safe_original_name,
    sha256_bytes,
    sha256_text,
    validate_upload,
)
from app.services.embeddings import EmbeddingsUnavailable, embed_texts
from app.services.jobs import mark_job
from app.services.vectors import (
    VectorIndexError,
    delete_points,
    upsert_points,
)

logger = logging.getLogger(__name__)

AUDIENCES = {"staff", "exec"}


class FaultInjected(RuntimeError):
    pass


@dataclass(frozen=True)
class UploadMeta:
    title: str
    category: str
    source_label: str
    audience: str
    effective_date: date
    slug: str | None = None


def ingest_upload(app_state, filename: str, content: bytes, meta: UploadMeta) -> str:
    settings: Settings = app_state.settings
    _debug_sleep(settings)
    _validate_meta(meta)
    extension = validate_upload(filename, content, settings)
    digest = sha256_bytes(content)
    session = app_state.session_factory()
    stored: Path | None = None
    try:
        ensure_reference_data(session)
        _reject_duplicate(session, digest)
        stored = _write_upload(settings, extension, content)
        document_id, version_id, job_id = _insert_new_document(
            session,
            meta=meta,
            filename=safe_original_name(filename, extension),
            stored=stored,
            extension=extension,
            content=content,
            digest=digest,
            is_current=True,
        )
        session.commit()
    except Exception:
        session.rollback()
        if stored is not None:
            stored.unlink(missing_ok=True)
        raise
    finally:
        session.close()
    _parse_and_index(
        app_state,
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        stored=stored,
        extension=extension,
        old_chunk_ids=[],
    )
    return document_id


def ingest_replacement(
    app_state,
    document_id: str,
    filename: str,
    content: bytes,
    *,
    effective_date: date,
    title: str | None,
) -> str:
    settings: Settings = app_state.settings
    _debug_sleep(settings)
    extension = validate_upload(filename, content, settings)
    digest = sha256_bytes(content)
    session = app_state.session_factory()
    stored: Path | None = None
    try:
        document = session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise AppError("not_found", "Document not found.", 404)
        _reject_duplicate(session, digest)
        if title:
            cleaned = title.strip()
            if not cleaned or len(cleaned) > 300:
                raise AppError("invalid_title", "Title must be 1 to 300 characters.", 400)
            document.title = cleaned
        stored = _write_upload(settings, extension, content)
        old_chunk_ids = list(
            session.scalars(
                select(Chunk.id).where(
                    Chunk.document_id == document_id,
                    Chunk.is_current.is_(True),
                )
            ).all()
        )
        version_id, job_id = _insert_version(
            session,
            document=document,
            filename=safe_original_name(filename, extension),
            stored=stored,
            extension=extension,
            content=content,
            digest=digest,
            effective_date=effective_date,
            is_current=False,
        )
        session.commit()
    except Exception:
        session.rollback()
        if stored is not None:
            stored.unlink(missing_ok=True)
        raise
    finally:
        session.close()

    try:
        parsed = parse_in_subprocess(stored, extension, settings)
    except HostileFile as exc:
        _fail_version(app_state.session_factory, version_id, job_id, exc.code, exc.message)
        stored.unlink(missing_ok=True)
        logger.info("replacement parse failed code=%s version=%s", exc.code, version_id)
        return document_id

    _index_parsed(
        app_state,
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        pages=parsed.pages,
        warning=parsed.warning,
        old_chunk_ids=old_chunk_ids,
    )
    return document_id


def _parse_and_index(
    app_state,
    *,
    document_id: str,
    version_id: str,
    job_id: str,
    stored: Path,
    extension: str,
    old_chunk_ids: list[str],
) -> None:
    settings: Settings = app_state.settings
    try:
        parsed = parse_in_subprocess(stored, extension, settings)
    except HostileFile as exc:
        _fail_version(app_state.session_factory, version_id, job_id, exc.code, exc.message)
        stored.unlink(missing_ok=True)
        logger.info("parse failed code=%s version=%s", exc.code, version_id)
        return
    _index_parsed(
        app_state,
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        pages=parsed.pages,
        warning=parsed.warning,
        old_chunk_ids=old_chunk_ids,
    )


def _index_parsed(
    app_state,
    *,
    document_id: str,
    version_id: str,
    job_id: str,
    pages: list[tuple[int, str]],
    warning: str | None,
    old_chunk_ids: list[str],
) -> None:
    drafts = chunk_pages(pages)
    if not drafts:
        _fail_version(
            app_state.session_factory,
            version_id,
            job_id,
            "empty_document",
            "No indexable text was found.",
        )
        return
    chunk_ids = [str(uuid4()) for _ in drafts]
    texts = [draft.text for draft in drafts]
    session = app_state.session_factory()
    try:
        now = utcnow()
        if old_chunk_ids:
            _supersede_current(session, document_id, version_id, old_chunk_ids, now)
        version = session.get(DocumentVersion, version_id)
        if version is None:
            raise AppError("not_found", "Document version not found.", 404)
        version.is_current = True
        version.page_count = len({page for page, _text in pages})
        version.indexing_state = "indexed"
        version.extraction_error = None
        version.extraction_warning = warning
        for draft, chunk_id in zip(drafts, chunk_ids, strict=True):
            counts, token_count = term_counts(draft.text)
            session.add(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    document_version_id=version_id,
                    ordinal=draft.ordinal,
                    page_number=draft.page_number,
                    section_title=draft.section_title,
                    text=draft.text,
                    text_sha256=sha256_text(draft.text),
                    token_count=token_count,
                    is_current=True,
                    superseded_at=None,
                    ingested_at=now,
                    instruction_override=is_instruction_override(draft.text),
                )
            )
            for term, frequency in counts.items():
                session.add(ChunkTerm(chunk_id=chunk_id, term=term[:80], tf=int(frequency)))
        bump_corpus_state(session)
        # PostgreSQL (or SQLite) is committed before any vector delete.
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    try:
        _sync_vectors(app_state, chunk_ids, texts, old_chunk_ids)
    except FaultInjected as exc:
        _mark_vector_gap(
            app_state.session_factory,
            version_id,
            job_id,
            reason=str(exc),
            job_status="FAILED",
            job_error=str(exc),
        )
        raise
    except (EmbeddingsUnavailable, VectorIndexError) as exc:
        _mark_vector_gap(
            app_state.session_factory,
            version_id,
            job_id,
            reason=exc.__class__.__name__,
            job_status="SUCCEEDED",
            job_error=None,
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.info("vector sync failed: %s", exc.__class__.__name__)
        _mark_vector_gap(
            app_state.session_factory,
            version_id,
            job_id,
            reason=exc.__class__.__name__,
            job_status="SUCCEEDED",
            job_error=None,
        )
        return
    session = app_state.session_factory()
    try:
        mark_job(session, job_id, "SUCCEEDED", None)
    finally:
        session.close()


def _sync_vectors(
    app_state, chunk_ids: list[str], texts: list[str], old_chunk_ids: list[str]
) -> None:
    settings: Settings = app_state.settings
    client = app_state.qdrant
    if old_chunk_ids and settings.fault_inject == "after_commit_before_vector_delete":
        # Intentional gap: the database already says the old chunks are not current.
        raise FaultInjected("injected fault before vector delete")
    if client is None:
        raise VectorIndexError("qdrant_unavailable")
    if old_chunk_ids:
        delete_points(client, settings, old_chunk_ids)
    vectors = embed_texts(texts, settings)
    upsert_points(client, settings, list(zip(chunk_ids, vectors, strict=True)))


def _supersede_current(
    session: Session,
    document_id: str,
    new_version_id: str,
    old_chunk_ids: list[str],
    now,
) -> None:
    versions = session.scalars(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_current.is_(True),
            DocumentVersion.id != new_version_id,
        )
    ).all()
    for version in versions:
        version.is_current = False
        version.superseded_at = now
    chunks = session.scalars(select(Chunk).where(Chunk.id.in_(old_chunk_ids))).all()
    for chunk in chunks:
        chunk.is_current = False
        chunk.superseded_at = now
    if old_chunk_ids:
        session.execute(delete(ChunkTerm).where(ChunkTerm.chunk_id.in_(old_chunk_ids)))


def _insert_new_document(
    session: Session,
    *,
    meta: UploadMeta,
    filename: str,
    stored: Path,
    extension: str,
    content: bytes,
    digest: str,
    is_current: bool,
) -> tuple[str, str, str]:
    now = utcnow()
    document = Document(
        id=str(uuid4()),
        slug=meta.slug,
        title=meta.title.strip(),
        category=meta.category,
        source_label=meta.source_label.strip(),
        audience=meta.audience,
        synthetic=True,
        created_at=now,
        deleted_at=None,
    )
    session.add(document)
    session.flush()
    version_id, job_id = _insert_version(
        session,
        document=document,
        filename=filename,
        stored=stored,
        extension=extension,
        content=content,
        digest=digest,
        effective_date=meta.effective_date,
        is_current=is_current,
    )
    return document.id, version_id, job_id


def _insert_version(
    session: Session,
    *,
    document: Document,
    filename: str,
    stored: Path,
    extension: str,
    content: bytes,
    digest: str,
    effective_date: date,
    is_current: bool,
) -> tuple[str, str]:
    now = utcnow()
    current_max = session.scalar(
        select(func.max(DocumentVersion.revision)).where(DocumentVersion.document_id == document.id)
    )
    revision = int(current_max or 0) + 1
    version = DocumentVersion(
        id=str(uuid4()),
        document_id=document.id,
        revision=revision,
        effective_date=effective_date,
        is_current=is_current,
        superseded_at=None,
        original_filename=filename,
        stored_path=str(stored),
        extension=extension,
        mime_type=MIME_TYPES[extension],
        byte_size=len(content),
        sha256=digest,
        page_count=None,
        indexing_state="pending",
        extraction_error=None,
        extraction_warning=None,
        created_at=now,
    )
    job = IngestionJob(
        id=str(uuid4()),
        document_version_id=version.id,
        status="RUNNING",
        heartbeat_at=now,
        error=None,
        created_at=now,
        started_at=now,
        finished_at=None,
    )
    session.add(version)
    session.add(job)
    return version.id, job.id


def _reject_duplicate(session: Session, digest: str) -> None:
    existing = session.scalar(
        select(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(DocumentVersion.sha256 == digest)
        .where(Document.deleted_at.is_(None))
    )
    if existing is None:
        return
    document = session.get(Document, existing.document_id)
    title = document.title if document is not None else "an existing document"
    raise AppError(
        "duplicate_upload",
        f"This file is already stored as {title} revision {existing.revision}.",
        409,
    )


def _validate_meta(meta: UploadMeta) -> None:
    title = meta.title.strip()
    if not title or len(title) > 300:
        raise AppError("invalid_title", "Title must be 1 to 300 characters.", 400)
    if meta.category not in {"company_policy", "regulatory_briefing"}:
        raise AppError("invalid_category", "Unknown document category.", 400)
    if meta.audience not in AUDIENCES:
        raise AppError("invalid_audience", "Audience must be staff or exec.", 400)
    source = meta.source_label.strip()
    if not source or len(source) > 200:
        raise AppError("invalid_source", "Source label must be 1 to 200 characters.", 400)


def _write_upload(settings: Settings, extension: str, content: bytes) -> Path:
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}{extension}"
    path.write_bytes(content)
    return path


def _debug_sleep(settings: Settings) -> None:
    if settings.ingest_debug_sleep_seconds > 0:
        import time

        time.sleep(settings.ingest_debug_sleep_seconds)


def _fail_version(
    factory: sessionmaker[Session],
    version_id: str,
    job_id: str,
    code: str,
    message: str,
) -> None:
    session = factory()
    try:
        version = session.get(DocumentVersion, version_id)
        job = session.get(IngestionJob, job_id)
        now = utcnow()
        if version is not None:
            version.indexing_state = "failed"
            version.extraction_error = message
        if job is not None:
            job.status = "FAILED"
            job.error = code
            job.heartbeat_at = now
            job.finished_at = now
        session.commit()
    finally:
        session.close()


def _mark_vector_gap(
    factory: sessionmaker[Session],
    version_id: str,
    job_id: str,
    *,
    reason: str,
    job_status: str,
    job_error: str | None,
) -> None:
    session = factory()
    try:
        version = session.get(DocumentVersion, version_id)
        if version is not None:
            version.indexing_state = "indexed_sparse"
            version.extraction_warning = (
                "Dense vectors were not updated "
                f"({reason}). Sparse search still includes the indexed text."
            )
        mark_job(session, job_id, job_status, job_error)
    finally:
        session.close()
