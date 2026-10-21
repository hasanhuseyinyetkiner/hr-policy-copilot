"""Hybrid retrieval. Database rows are the source of truth for every hit."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.bm25 import load_corpus_stats, sparse_search
from app.domain.evidence import ScoredChunk
from app.domain.fusion import reciprocal_rank_fusion, rrf_list_contributions
from app.domain.tokenize import tokenize, unique_tokens
from app.models import Chunk, Document, DocumentVersion
from app.services.embeddings import EmbeddingsUnavailable, embed_texts, model_status
from app.services.vectors import search_points


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    document: Document
    version: DocumentVersion
    scored: ScoredChunk
    bm25_rrf_contrib: float = 0.0
    dense_rrf_contrib: float = 0.0


@dataclass(frozen=True)
class FilterRejection:
    chunk_id: str
    reason: str


@dataclass(frozen=True)
class RetrievalTelemetry:
    corpus_version: int
    latency_ms: float
    embedding_backend: str
    preference: str
    mode: str
    dense_available: bool
    dense_error: str | None
    bm25_candidates: int
    dense_candidates: int
    fused_candidates: int
    filter_rejected: int
    filter_rejections: list[FilterRejection] = field(default_factory=list)
    query_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalResult:
    hits: list[RetrievalHit]
    mode: str
    dense_available: bool
    dense_error: str | None
    query_terms: list[str]
    telemetry: RetrievalTelemetry


def retrieve(
    session: Session,
    app_state,
    question: str,
    *,
    categories: list[str] | None,
    audience: str,
    preference: str = "hybrid",
) -> RetrievalResult:
    """Retrieve current chunks. ``preference`` is hybrid|dense|sparse (eval / ablation)."""
    started = time.perf_counter()
    if preference not in {"hybrid", "dense", "sparse"}:
        preference = "hybrid"
    settings: Settings = app_state.settings
    query_terms = unique_tokens(question)
    corpus_version = load_corpus_stats(session).corpus_version
    sparse = sparse_search(
        session,
        query_terms,
        categories=categories,
        audience=audience,
        limit=settings.retrieval_candidate_limit,
        k1=settings.bm25_k1,
        b=settings.bm25_b,
    )
    sparse_scores = dict(sparse)
    dense_scores: dict[str, float] = {}
    dense_ids: list[str] = []
    dense_error: str | None = None
    run_dense = preference != "sparse"
    ready, ready_detail = model_status(settings)
    if run_dense:
        if not ready:
            dense_error = ready_detail
        elif app_state.qdrant is None:
            dense_error = "qdrant_unavailable"
        else:
            try:
                vector = embed_texts([question], settings)[0]
                found = search_points(
                    app_state.qdrant,
                    settings,
                    vector,
                    settings.retrieval_candidate_limit,
                )
                for chunk_id, score in found:
                    dense_ids.append(chunk_id)
                    dense_scores[chunk_id] = score
            except EmbeddingsUnavailable as exc:
                dense_error = exc.message
            except Exception as exc:  # noqa: BLE001
                dense_error = exc.__class__.__name__

    ordered_ids: list[str] = []
    for chunk_id, _score in sparse:
        if chunk_id not in ordered_ids:
            ordered_ids.append(chunk_id)
    for chunk_id in dense_ids:
        if chunk_id not in ordered_ids:
            ordered_ids.append(chunk_id)
    allowed = post_filter_chunks(
        session,
        ordered_ids,
        categories=categories,
        audience=audience,
    )
    rejections = _filter_rejections(session, ordered_ids, allowed)
    sparse_ranked = [chunk_id for chunk_id, _score in sparse if chunk_id in allowed]
    dense_ranked = [chunk_id for chunk_id in dense_ids if chunk_id in allowed]
    if preference == "sparse" or dense_error is not None:
        rankings = [sparse_ranked]
        mode = "sparse"
        contrib_lists = ["bm25"]
    elif preference == "dense":
        rankings = [dense_ranked]
        mode = "dense"
        contrib_lists = ["dense"]
    else:
        rankings = [dense_ranked, sparse_ranked]
        mode = "hybrid"
        contrib_lists = ["dense", "bm25"]
    fused = reciprocal_rank_fusion(rankings, k=settings.rrf_k)
    contrib_map = rrf_list_contributions(rankings, k=settings.rrf_k)
    hits: list[RetrievalHit] = []
    query_set = set(query_terms)
    for chunk_id, rrf_score in fused:
        chunk, document, version = allowed[chunk_id]
        overlap = len(query_set.intersection(tokenize(chunk.text)))
        parts = contrib_map.get(chunk_id, [0.0] * len(contrib_lists))
        dense_contrib = 0.0
        bm25_contrib = 0.0
        for list_name, value in zip(contrib_lists, parts, strict=True):
            if list_name == "dense":
                dense_contrib = value
            elif list_name == "bm25":
                bm25_contrib = value
        scored = ScoredChunk(
            chunk_id=chunk_id,
            text=chunk.text,
            overlap=overlap,
            bm25=float(sparse_scores.get(chunk_id, 0.0)),
            dense=dense_scores.get(chunk_id),
            rrf=float(rrf_score),
            instruction_override=bool(chunk.instruction_override),
        )
        hits.append(
            RetrievalHit(
                chunk=chunk,
                document=document,
                version=version,
                scored=scored,
                bm25_rrf_contrib=bm25_contrib,
                dense_rrf_contrib=dense_contrib,
            )
        )
    dense_stack_ok = dense_error is None if run_dense else (
        ready and app_state.qdrant is not None
    )
    latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    telemetry = RetrievalTelemetry(
        corpus_version=corpus_version,
        latency_ms=latency_ms,
        embedding_backend=settings.embedding_backend,
        preference=preference,
        mode=mode,
        dense_available=dense_stack_ok,
        dense_error=dense_error,
        bm25_candidates=len(sparse),
        dense_candidates=len(dense_ids),
        fused_candidates=len(fused),
        filter_rejected=len(rejections),
        filter_rejections=rejections,
        query_terms=query_terms,
    )
    return RetrievalResult(
        hits=hits,
        mode=mode,
        dense_available=dense_stack_ok,
        dense_error=dense_error,
        query_terms=query_terms,
        telemetry=telemetry,
    )


def _filter_rejections(
    session: Session,
    ordered_ids: list[str],
    allowed: dict[str, tuple[Chunk, Document, DocumentVersion]],
) -> list[FilterRejection]:
    rejected_ids = [chunk_id for chunk_id in ordered_ids if chunk_id not in allowed]
    if not rejected_ids:
        return []
    rows = session.execute(
        select(Chunk, Document, DocumentVersion)
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .where(Chunk.id.in_(rejected_ids))
    ).all()
    by_id = {chunk.id: (chunk, document, version) for chunk, document, version in rows}
    out: list[FilterRejection] = []
    for chunk_id in rejected_ids:
        row = by_id.get(chunk_id)
        if row is None:
            out.append(FilterRejection(chunk_id=chunk_id, reason="missing_from_database"))
            continue
        chunk, document, version = row
        if document.deleted_at is not None:
            reason = "document_deleted"
        elif not version.is_current:
            reason = "version_not_current"
        elif not chunk.is_current:
            reason = "chunk_not_current"
        else:
            reason = "audience_or_category_filter"
        out.append(FilterRejection(chunk_id=chunk_id, reason=reason))
    return out


def post_filter_chunks(
    session: Session,
    chunk_ids: list[str],
    *,
    categories: list[str] | None,
    audience: str,
) -> dict[str, tuple[Chunk, Document, DocumentVersion]]:
    """Drop any hit the database does not currently allow to be shown or cited."""
    if not chunk_ids:
        return {}
    statement = (
        select(Chunk, Document, DocumentVersion)
        .join(Document, Document.id == Chunk.document_id)
        .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
        .where(Chunk.id.in_(chunk_ids))
        .where(Chunk.is_current.is_(True))
        .where(DocumentVersion.is_current.is_(True))
        .where(Document.deleted_at.is_(None))
        .where(Document.audience == audience)
    )
    if categories:
        statement = statement.where(Document.category.in_(categories))
    rows = session.execute(statement).all()
    return {chunk.id: (chunk, document, version) for chunk, document, version in rows}
