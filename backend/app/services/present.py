"""Read models into API schemas."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import EMBEDDING_LICENSE, EXAMPLES, LIMITATIONS
from app.db import CATEGORY_ROWS
from app.domain.bm25 import load_corpus_stats
from app.errors import AppError
from app.models import (
    Category,
    Chunk,
    Conversation,
    Document,
    DocumentVersion,
    Message,
)
from app.schemas import (
    CategoryOut,
    ChunkOut,
    ConversationOut,
    ConversationSummary,
    DocumentOut,
    MessageOut,
    OverviewOut,
    RetrievalStatus,
    SettingsOut,
    VersionOut,
    VersionTextOut,
)
from app.services.answering import extras_from_message, load_message_citations
from app.services.embeddings import model_status
from app.services.vectors import qdrant_status


def list_documents(session: Session, *, include_deleted: bool = False) -> list[DocumentOut]:
    statement = select(Document).order_by(Document.created_at.desc())
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    documents = list(session.scalars(statement).all())
    return _serialize_many(session, documents)


def get_document(session: Session, document_id: str) -> DocumentOut:
    document = session.get(Document, document_id)
    if document is None:
        raise AppError("not_found", "Document not found.", 404)
    return _serialize_many(session, [document])[0]


def list_versions(session: Session, document_id: str) -> list[VersionOut]:
    document = session.get(Document, document_id)
    if document is None:
        raise AppError("not_found", "Document not found.", 404)
    versions = session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.revision.desc())
    ).all()
    return [_version_out(version) for version in versions]


def version_text(session: Session, document_id: str, version_id: str) -> VersionTextOut:
    document = session.get(Document, document_id)
    version = session.get(DocumentVersion, version_id)
    if document is None or version is None or version.document_id != document_id:
        raise AppError("not_found", "Document version not found.", 404)
    chunks = session.scalars(
        select(Chunk).where(Chunk.document_version_id == version_id).order_by(Chunk.ordinal)
    ).all()
    return VersionTextOut(
        document=_serialize_many(session, [document])[0],
        version=_version_out(version),
        chunks=[
            ChunkOut(
                id=chunk.id,
                ordinal=chunk.ordinal,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                text=chunk.text,
                text_sha256=chunk.text_sha256,
                is_current=chunk.is_current,
                instruction_override=chunk.instruction_override,
            )
            for chunk in chunks
        ],
    )


def overview(session: Session, app_state) -> OverviewOut:
    documents = list_documents(session)
    version_count = int(
        session.scalar(
            select(func.count())
            .select_from(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(Document.deleted_at.is_(None))
        )
        or 0
    )
    chunk_count = int(
        session.scalar(select(func.count()).select_from(Chunk).where(Chunk.is_current.is_(True)))
        or 0
    )
    conversation_count = int(session.scalar(select(func.count()).select_from(Conversation)) or 0)
    categories = _category_counts(session)
    in_use = sum(1 for category in categories if category.document_count > 0)
    stats = load_corpus_stats(session)
    dense_ready, _detail = model_status(app_state.settings)
    qdrant_ready, _qdetail = qdrant_status(app_state.qdrant, app_state.settings)
    recent = sorted(
        documents,
        key=lambda item: item.updated_at.isoformat() if item.updated_at else "",
        reverse=True,
    )[:5]
    return OverviewOut(
        documents=len(documents),
        versions=version_count,
        categories_in_use=in_use,
        chunks=chunk_count,
        conversations=conversation_count,
        categories=categories,
        recent_documents=recent,
        examples=list(EXAMPLES),
        retrieval=RetrievalStatus(
            corpus_version=stats.corpus_version,
            dense_ready=dense_ready and qdrant_ready,
            qdrant_ready=qdrant_ready,
            mode="hybrid" if dense_ready and qdrant_ready else "sparse",
        ),
        demo=app_state.settings.app_env == "demo",
    )


def settings_out(app_state) -> SettingsOut:
    ready, _detail = model_status(app_state.settings)
    host = app_state.settings.api_host.strip().lower()
    return SettingsOut(
        app_env=app_state.settings.app_env,
        llm_mode="extractive",
        external_llm_calls=False,
        embedding_model=app_state.settings.embedding_model,
        embedding_dimensions=app_state.settings.embedding_dimensions,
        embedding_license=EMBEDDING_LICENSE,
        embedding_ready=ready,
        retrieval="hybrid reciprocal rank fusion of dense vectors and database BM25",
        loopback_only=host in {"127.0.0.1", "localhost", "::1"},
        limitations=list(LIMITATIONS),
    )


def list_conversations(session: Session) -> list[ConversationSummary]:
    conversations = session.scalars(
        select(Conversation).order_by(Conversation.created_at.desc())
    ).all()
    summaries: list[ConversationSummary] = []
    for conversation in conversations:
        count = int(
            session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation.id)
            )
            or 0
        )
        summaries.append(
            ConversationSummary(
                id=conversation.id,
                title=conversation.title,
                created_at=conversation.created_at,
                message_count=count,
            )
        )
    return summaries


def get_conversation(session: Session, conversation_id: str) -> ConversationOut:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise AppError("not_found", "Conversation not found.", 404)
    messages = session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    ).all()
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=[_message_out(session, message) for message in messages],
    )


def _message_out(session: Session, message: Message) -> MessageOut:
    extras = extras_from_message(message)
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        mode=message.mode,
        retrieval_mode=message.retrieval_mode,
        contradictory=message.contradictory,
        conflict_note=message.conflict_note,
        notice=message.notice,
        dense_available=message.dense_available,
        preamble=extras.preamble if extras else None,
        abstention_reason=extras.abstention_reason if extras else None,
        citations=load_message_citations(session, message.id),
        evidence=extras.evidence if extras else [],
        superseded=extras.superseded if extras else [],
        evidence_thresholds=extras.evidence_thresholds if extras else None,
        created_at=message.created_at,
    )


def _serialize_many(session: Session, documents: list[Document]) -> list[DocumentOut]:
    if not documents:
        return []
    ids = [document.id for document in documents]
    versions = session.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id.in_(ids))
    ).all()
    by_document: dict[str, list[DocumentVersion]] = {}
    for version in versions:
        by_document.setdefault(version.document_id, []).append(version)
    version_ids = [version.id for version in versions]
    counts = {}
    if version_ids:
        counts = dict(
            session.execute(
                select(Chunk.document_version_id, func.count())
                .where(Chunk.document_version_id.in_(version_ids))
                .where(Chunk.is_current.is_(True))
                .group_by(Chunk.document_version_id)
            ).all()
        )
    categories = {row.key: row for row in session.scalars(select(Category)).all()}
    outputs: list[DocumentOut] = []
    for document in documents:
        document_versions = by_document.get(document.id, [])
        current = next((version for version in document_versions if version.is_current), None)
        chosen = current
        if chosen is None and document_versions:
            chosen = max(document_versions, key=lambda version: version.revision)
        category = categories.get(document.category)
        label = category.label if category is not None else document.category
        policy_id = document.slug if document.slug and document.slug.startswith("POL-") else None
        outputs.append(
            DocumentOut(
                id=document.id,
                title=document.title,
                policy_id=policy_id,
                category=document.category,
                category_label=label,
                source_label=document.source_label,
                audience=document.audience,
                synthetic=document.synthetic,
                deleted=document.deleted_at is not None,
                current_revision=chosen.revision if chosen else None,
                version_id=chosen.id if chosen else None,
                effective_date=chosen.effective_date if chosen else None,
                page_count=chosen.page_count if chosen else None,
                indexing_state=chosen.indexing_state if chosen else None,
                extraction_error=chosen.extraction_error if chosen else None,
                extraction_warning=chosen.extraction_warning if chosen else None,
                chunk_count=int(counts.get(chosen.id, 0)) if chosen else 0,
                original_filename=chosen.original_filename if chosen else None,
                updated_at=chosen.created_at if chosen else document.created_at,
            )
        )
    return outputs


def _version_out(version: DocumentVersion) -> VersionOut:
    return VersionOut(
        id=version.id,
        revision=version.revision,
        effective_date=version.effective_date,
        is_current=version.is_current,
        superseded_at=version.superseded_at,
        page_count=version.page_count,
        indexing_state=version.indexing_state,
        extraction_error=version.extraction_error,
        extraction_warning=version.extraction_warning,
        sha256=version.sha256,
        original_filename=version.original_filename,
        byte_size=version.byte_size,
        created_at=version.created_at,
    )


def _category_counts(session: Session) -> list[CategoryOut]:
    rows = list(session.scalars(select(Category)).all())
    if not rows:
        rows = [
            Category(key=key, label=label, description=description)
            for key, label, description in CATEGORY_ROWS
        ]
    outputs: list[CategoryOut] = []
    for category in rows:
        count = int(
            session.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.category == category.key)
                .where(Document.deleted_at.is_(None))
            )
            or 0
        )
        outputs.append(
            CategoryOut(
                key=category.key,
                label=category.label,
                description=category.description,
                document_count=count,
            )
        )
    return outputs
