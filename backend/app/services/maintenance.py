"""Demo reset and document deletion."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import BUSINESS_TABLES, bump_corpus_state, ensure_reference_data, utcnow
from app.errors import AppError
from app.models import (
    Chunk,
    ChunkTerm,
    Citation,
    Conversation,
    CorpusState,
    Document,
    DocumentVersion,
    IngestionJob,
    Message,
)
from app.services.vectors import delete_points, reset_collection

logger = logging.getLogger(__name__)

_DELETE_ORDER = (
    Citation,
    Message,
    Conversation,
    ChunkTerm,
    Chunk,
    IngestionJob,
    DocumentVersion,
    Document,
    CorpusState,
)


def delete_document(app_state, document_id: str) -> None:
    session: Session = app_state.session_factory()
    chunk_ids: list[str] = []
    try:
        document = session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise AppError("not_found", "Document not found.", 404)
        now = utcnow()
        document.deleted_at = now
        chunk_ids = list(
            session.scalars(
                select(Chunk.id).where(
                    Chunk.document_id == document_id,
                    Chunk.is_current.is_(True),
                )
            ).all()
        )
        versions = session.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_current.is_(True),
            )
        ).all()
        for version in versions:
            version.is_current = False
            version.superseded_at = now
        if chunk_ids:
            chunks = session.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
            for chunk in chunks:
                chunk.is_current = False
                chunk.superseded_at = now
            session.execute(delete(ChunkTerm).where(ChunkTerm.chunk_id.in_(chunk_ids)))
        bump_corpus_state(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    if chunk_ids and app_state.qdrant is not None:
        try:
            delete_points(app_state.qdrant, app_state.settings, chunk_ids)
        except Exception:  # noqa: BLE001
            logger.info("vector delete failed after document delete")


def wipe_business_data(app_state) -> None:
    session: Session = app_state.session_factory()
    try:
        for model in _DELETE_ORDER:
            session.execute(delete(model))
        session.commit()
        ensure_reference_data(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    root = Path(app_state.settings.upload_dir).resolve()
    if root.exists():
        for path in root.iterdir():
            if path.is_file() and path.resolve().is_relative_to(root):
                path.unlink()
    if app_state.qdrant is not None:
        try:
            reset_collection(app_state.qdrant, app_state.settings)
        except Exception:  # noqa: BLE001
            logger.info("qdrant reset failed")


def assert_demo(app_state) -> None:
    if app_state.settings.app_env != "demo":
        raise AppError("demo_only", "This action is only available when APP_ENV=demo.", 403)


def table_names() -> tuple[str, ...]:
    return BUSINESS_TABLES
