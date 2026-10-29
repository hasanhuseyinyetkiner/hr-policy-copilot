"""Extractive answers, abstention, and citation snapshots."""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import ensure_reference_data, utcnow
from app.domain.contradictions import conflicting_office_days
from app.domain.evidence import Thresholds, choose_passages, passes_threshold
from app.domain.tokenize import tokenize
from app.errors import AppError
from app.models import Chunk, Citation, Conversation, Document, DocumentVersion, Message
from app.parsing.uploads import sha256_text
from app.schemas import (
    CitationOut,
    EvidenceOut,
    EvidenceThresholdsOut,
    FilterRejectionOut,
    MessageExtras,
    QueryOut,
    RetrievalTelemetryOut,
    SupersededHint,
)
from app.services.retrieval import RetrievalHit, RetrievalTelemetry, retrieve

EXTRACT_PREAMBLE = (
    "Quoted directly from indexed policy text. This is not a generated explanation "
    "and it is not legal advice."
)
ABSTAIN_PREAMBLE = (
    "No answer is shown because the indexed policies did not clear the evidence threshold."
)
SPARSE_NOTICE = "Dense retrieval is unavailable. This answer uses sparse search only."
HISTORICAL_PREAMBLE = (
    "This search only answers from current policy versions. Historical or explicitly numbered "
    "versions cannot be answered here; inspect the document's version history."
)


def _requests_version_scope(question: str) -> bool:
    """Conservatively reject version-scoped requests that current-only search cannot honor."""
    return bool(re.search(
        r"\b(?:revision|version)\s*(?:#\s*)?v?\d+\b"
        r"|\b(?:previous|prior|earlier|older|old|superseded|historical|first|second|third)\s+"
        r"(?:policy\s+)?(?:revision|version|edition|policy)\b"
        r"|\b(?:revision|version)\s+(?:history|before|prior to)\b",
        question, re.IGNORECASE,
    ))


def answer_question(
    app_state,
    *,
    question: str,
    conversation_id: str | None,
    categories: list[str] | None,
    audience: str,
    retrieval_preference: str = "hybrid",
) -> QueryOut:
    if audience not in {"staff", "exec"}:
        raise AppError("invalid_audience", "Audience must be staff or exec.", 400)
    if retrieval_preference not in {"hybrid", "dense", "sparse"}:
        raise AppError(
            "invalid_retrieval_preference",
            "retrieval_preference must be hybrid, dense, or sparse.",
            400,
        )
    cleaned_categories = _clean_categories(categories)
    session = app_state.session_factory()
    try:
        ensure_reference_data(session)
        _validate_categories(session, cleaned_categories)
        conversation = _conversation(session, conversation_id, question)
        session.add(
            Message(
                id=str(uuid4()),
                conversation_id=conversation.id,
                role="user",
                content=question.strip(),
                mode=None,
                retrieval_mode=None,
                contradictory=False,
                conflict_note=None,
                notice=None,
                dense_available=None,
                extras_json=None,
                created_at=utcnow(),
            )
        )
        result = retrieve(
            session,
            app_state,
            question,
            categories=cleaned_categories,
            audience=audience,
            preference=retrieval_preference,
        )
        thresholds = Thresholds(
            min_overlap=app_state.settings.evidence_min_overlap,
            min_bm25=app_state.settings.evidence_min_bm25,
            min_cosine=app_state.settings.evidence_min_cosine,
            max_passages=app_state.settings.max_passages,
        )
        chosen, contradictory = choose_passages(
            [hit.scored for hit in result.hits],
            thresholds,
        )
        by_id = {hit.scored.chunk_id: hit for hit in result.hits}
        chosen_hits = [by_id[item.chunk_id] for item in chosen]
        version_scoped = _requests_version_scope(question)
        if version_scoped:
            chosen_hits = []
        abstention = (
            "unsupported_version_scope" if version_scoped else _abstention_reason(session, chosen_hits)
        )
        conflict_note = _conflict_note(chosen_hits) if contradictory else None
        superseded = _superseded_hints(
            session,
            result.query_terms,
            categories=cleaned_categories,
            audience=audience,
        )
        notice = SPARSE_NOTICE if not result.dense_available else None
        preamble = HISTORICAL_PREAMBLE if version_scoped else (
            EXTRACT_PREAMBLE if chosen_hits else ABSTAIN_PREAMBLE
        )
        if chosen_hits:
            content = preamble + "\n\n" + "\n\n".join(hit.chunk.text for hit in chosen_hits)
            mode = "extractive"
        else:
            content = preamble
            mode = "abstain"
        evidence = _evidence_rows(
            result.hits, {hit.chunk.id for hit in chosen_hits}, thresholds,
            version_scoped=version_scoped,
        )
        threshold_out = EvidenceThresholdsOut(
            min_overlap=thresholds.min_overlap,
            min_bm25=thresholds.min_bm25,
            min_cosine=thresholds.min_cosine,
            max_passages=thresholds.max_passages,
        )
        threshold_decision = (
            "cite"
            if chosen_hits
            else ("unsupported_version_scope" if version_scoped else
                  "no_documents" if abstention == "no_documents" else "abstain_below_threshold")
        )
        telemetry = _telemetry_out(result.telemetry, threshold_decision=threshold_decision)
        message = Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=content,
            mode=mode,
            retrieval_mode=result.mode,
            contradictory=contradictory and bool(chosen_hits),
            conflict_note=conflict_note,
            notice=notice,
            dense_available=result.dense_available,
            extras_json=MessageExtras(
                preamble=preamble,
                abstention_reason=abstention,
                evidence=evidence,
                superseded=superseded,
                evidence_thresholds=threshold_out,
                retrieval_telemetry=telemetry,
            ).model_dump_json(),
            created_at=utcnow(),
        )
        session.add(message)
        session.flush()
        citations = _store_citations(session, message.id, chosen_hits)
        session.commit()
        return QueryOut(
            conversation_id=conversation.id,
            id=message.id,
            role="assistant",
            content=content,
            mode=mode,
            retrieval_mode=result.mode,
            contradictory=bool(message.contradictory),
            conflict_note=conflict_note,
            notice=notice,
            dense_available=result.dense_available,
            preamble=preamble,
            abstention_reason=abstention,
            citations=citations,
            evidence=evidence,
            superseded=superseded,
            evidence_thresholds=threshold_out,
            retrieval_telemetry=telemetry,
            created_at=message.created_at,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _clean_categories(categories: list[str] | None) -> list[str] | None:
    if not categories:
        return None
    return categories


def _validate_categories(session: Session, categories: list[str] | None) -> None:
    if not categories:
        return
    from app.models import Category

    known = set(session.scalars(select(Category.key)).all())
    unknown = [item for item in categories if item not in known]
    if unknown:
        raise AppError("invalid_category", "Unknown category filter.", 400)


def _conversation(session: Session, conversation_id: str | None, question: str) -> Conversation:
    if conversation_id:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise AppError("not_found", "Conversation not found.", 404)
        return conversation
    conversation = Conversation(
        id=str(uuid4()),
        title=question.strip()[:180],
        created_at=utcnow(),
    )
    session.add(conversation)
    session.flush()
    return conversation


def _abstention_reason(session: Session, chosen: list[RetrievalHit]) -> str | None:
    if chosen:
        return None
    documents = int(
        session.scalar(
            select(func.count()).select_from(Document).where(Document.deleted_at.is_(None))
        )
        or 0
    )
    if documents == 0:
        return "no_documents"
    return "below_threshold"


def _conflict_note(chosen: list[RetrievalHit]) -> str | None:
    claims = sorted(conflicting_office_days([hit.chunk.text for hit in chosen]))
    if len(claims) < 2:
        return None
    rendered = " and ".join(str(value) for value in claims)
    return (
        f"These current sources state different in-office day requirements ({rendered}). "
        "Both are quoted. The demo does not choose between them."
    )


def _store_citations(
    session: Session,
    message_id: str,
    chosen: list[RetrievalHit],
) -> list[CitationOut]:
    outputs: list[CitationOut] = []
    for rank, hit in enumerate(chosen, start=1):
        snippet = hit.chunk.text
        digest = sha256_text(snippet)
        citation = Citation(
            id=str(uuid4()),
            message_id=message_id,
            chunk_id=hit.chunk.id,
            document_id=hit.document.id,
            document_version_id=hit.version.id,
            document_title=hit.document.title,
            category=hit.document.category,
            source_label=hit.document.source_label,
            revision=hit.version.revision,
            section_title=hit.chunk.section_title,
            page_number=hit.chunk.page_number,
            snippet=snippet,
            snippet_sha256=digest,
            effective_date=hit.version.effective_date,
            rank=rank,
            rrf_score=_round(hit.scored.rrf),
            bm25_score=_round(hit.scored.bm25),
            dense_score=_round(hit.scored.dense) if hit.scored.dense is not None else None,
        )
        session.add(citation)
        outputs.append(_citation_out(citation))
    return outputs


def _citation_out(citation: Citation) -> CitationOut:
    return CitationOut(
        id=citation.id,
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        document_version_id=citation.document_version_id,
        document_title=citation.document_title,
        category=citation.category,
        source_label=citation.source_label,
        revision=citation.revision,
        section_title=citation.section_title,
        page_number=citation.page_number,
        snippet=citation.snippet,
        snippet_sha256=citation.snippet_sha256,
        effective_date=citation.effective_date,
        rank=citation.rank,
        rrf_score=citation.rrf_score,
        bm25_score=citation.bm25_score,
        dense_score=citation.dense_score,
    )


def _evidence_rows(
    hits: list[RetrievalHit],
    chosen_ids: set[str],
    thresholds: Thresholds,
    *,
    version_scoped: bool = False,
) -> list[EvidenceOut]:
    ordered = sorted(hits, key=lambda hit: (-hit.scored.rrf, hit.scored.chunk_id))
    visible = ordered[:8]
    visible_ids = {hit.chunk.id for hit in visible}
    for hit in ordered:
        if hit.chunk.id in chosen_ids and hit.chunk.id not in visible_ids:
            visible.append(hit)
    rows: list[EvidenceOut] = []
    for hit in visible:
        used = hit.chunk.id in chosen_ids
        if used:
            reason = None
        elif hit.scored.instruction_override:
            reason = "instruction_override"
        elif not passes_threshold(hit.scored, thresholds):
            reason = "below_evidence_threshold"
        elif version_scoped:
            reason = "unsupported_version_scope"
        else:
            reason = "not_in_top_passages"
        preview = hit.chunk.text[:180]
        clears_overlap = hit.scored.overlap >= thresholds.min_overlap
        clears_bm25 = hit.scored.bm25 >= thresholds.min_bm25
        clears_dense = (hit.scored.dense or 0.0) >= thresholds.min_cosine
        rows.append(
            EvidenceOut(
                chunk_id=hit.chunk.id,
                document_id=hit.document.id,
                document_title=hit.document.title,
                revision=hit.version.revision,
                section_title=hit.chunk.section_title,
                page_number=hit.chunk.page_number,
                bm25_score=_round(hit.scored.bm25),
                dense_score=_round(hit.scored.dense) if hit.scored.dense is not None else None,
                rrf_score=_round(hit.scored.rrf),
                bm25_rrf_contrib=_round(hit.bm25_rrf_contrib),
                dense_rrf_contrib=_round(hit.dense_rrf_contrib),
                overlap=hit.scored.overlap,
                used=used,
                rejected_reason=reason,
                preview=preview,
                clears_overlap=clears_overlap,
                clears_bm25=clears_bm25,
                clears_dense=clears_dense,
                clears_abstention_gate=passes_threshold(hit.scored, thresholds),
            )
        )
    return rows


def _telemetry_out(
    telemetry: RetrievalTelemetry,
    *,
    threshold_decision: str,
) -> RetrievalTelemetryOut:
    return RetrievalTelemetryOut(
        corpus_version=telemetry.corpus_version,
        latency_ms=telemetry.latency_ms,
        embedding_backend=telemetry.embedding_backend,
        preference=telemetry.preference,
        mode=telemetry.mode if telemetry.mode in {"hybrid", "sparse", "dense"} else "sparse",
        dense_available=telemetry.dense_available,
        dense_error=telemetry.dense_error,
        bm25_candidates=telemetry.bm25_candidates,
        dense_candidates=telemetry.dense_candidates,
        fused_candidates=telemetry.fused_candidates,
        filter_rejected=telemetry.filter_rejected,
        filter_rejections=[
            FilterRejectionOut(chunk_id=item.chunk_id, reason=item.reason)
            for item in telemetry.filter_rejections[:12]
        ],
        query_terms=list(telemetry.query_terms),
        threshold_decision=threshold_decision,
    )


def _superseded_hints(
    session: Session,
    query_terms: list[str],
    *,
    categories: list[str] | None,
    audience: str,
) -> list[SupersededHint]:
    if not query_terms:
        return []
    statement = (
        select(Chunk, Document, DocumentVersion)
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .where(Chunk.is_current.is_(False))
        .where(Document.deleted_at.is_(None))
        .where(Document.audience == audience)
    )
    if categories:
        statement = statement.where(Document.category.in_(categories))
    query_set = set(query_terms)
    best: tuple[int, Chunk, Document, DocumentVersion] | None = None
    for chunk, document, version in session.execute(statement).all():
        if chunk.instruction_override:
            continue
        overlap = len(query_set.intersection(tokenize(chunk.text)))
        if overlap < 3:
            continue
        if best is None or overlap > best[0]:
            best = (overlap, chunk, document, version)
    if best is None:
        return []
    _overlap, _chunk, document, version = best
    current = session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current.is_(True),
        )
    )
    current_revision = current.revision if current is not None else None
    note = (
        f"{document.title} revision {version.revision} "
        f"(effective {version.effective_date.isoformat()}) was superseded and is not used as evidence."
    )
    if current_revision is not None:
        note += f" The current revision is {current_revision}."
    return [
        SupersededHint(
            document_id=document.id,
            document_version_id=version.id,
            document_title=document.title,
            revision=version.revision,
            effective_date=version.effective_date,
            current_revision=current_revision,
            note=note,
        )
    ]


def _round(value: float) -> float:
    return round(float(value), 4)


def load_message_citations(session: Session, message_id: str) -> list[CitationOut]:
    rows = session.scalars(
        select(Citation).where(Citation.message_id == message_id).order_by(Citation.rank)
    ).all()
    return [_citation_out(row) for row in rows]


def extras_from_message(message: Message) -> MessageExtras | None:
    if not message.extras_json:
        return None
    return MessageExtras.model_validate_json(message.extras_json)
