"""Okapi BM25 over term statistics stored in the database.

There is no process-local inverted index. Every score is computed from
``chunk_terms`` and current chunk rows, so two processes that share a
database see the same corpus.
"""

import math
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.tokenize import tokenize
from app.models import Chunk, ChunkTerm, CorpusState, Document


@dataclass(frozen=True)
class CorpusStats:
    corpus_version: int
    n_docs: int
    avgdl: float


def idf(n_docs: int, document_frequency: int) -> float:
    return math.log(1.0 + (n_docs - document_frequency + 0.5) / (document_frequency + 0.5))


def bm25_tf(
    tf: int,
    doc_length: int,
    avgdl: float,
    idf_value: float,
    *,
    k1: float,
    b: float,
) -> float:
    average = avgdl if avgdl > 0 else 1.0
    denominator = tf + k1 * (1.0 - b + b * (doc_length / average))
    if denominator == 0:
        return 0.0
    return idf_value * (tf * (k1 + 1.0) / denominator)


def score_terms(
    term_frequencies: dict[str, int],
    *,
    doc_length: int,
    avgdl: float,
    n_docs: int,
    document_frequencies: dict[str, int],
    query_terms: list[str],
    k1: float,
    b: float,
) -> float:
    score = 0.0
    for term in query_terms:
        tf = term_frequencies.get(term, 0)
        if tf <= 0:
            continue
        df = document_frequencies.get(term, 0)
        score += bm25_tf(tf, doc_length, avgdl, idf(n_docs, df), k1=k1, b=b)
    return score


def load_corpus_stats(session: Session) -> CorpusStats:
    state = session.get(CorpusState, 1)
    version = state.corpus_version if state is not None else 0
    n_docs = int(
        session.scalar(select(func.count()).select_from(Chunk).where(Chunk.is_current.is_(True)))
        or 0
    )
    average = session.scalar(select(func.avg(Chunk.token_count)).where(Chunk.is_current.is_(True)))
    return CorpusStats(corpus_version=version, n_docs=n_docs, avgdl=float(average or 0.0))


def document_frequencies(session: Session, terms: list[str]) -> dict[str, int]:
    if not terms:
        return {}
    rows = session.execute(
        select(ChunkTerm.term, func.count(func.distinct(ChunkTerm.chunk_id)))
        .join(Chunk, Chunk.id == ChunkTerm.chunk_id)
        .where(Chunk.is_current.is_(True))
        .where(ChunkTerm.term.in_(terms))
        .group_by(ChunkTerm.term)
    ).all()
    return {term: int(count) for term, count in rows}


def sparse_search(
    session: Session,
    query_terms: list[str],
    *,
    categories: list[str] | None,
    audience: str,
    limit: int,
    k1: float,
    b: float,
) -> list[tuple[str, float]]:
    """Return ``(chunk_id, bm25)`` for current chunks, highest score first."""
    if not query_terms:
        return []
    stats = load_corpus_stats(session)
    if stats.n_docs == 0:
        return []
    frequencies = document_frequencies(session, query_terms)
    statement = (
        select(ChunkTerm.chunk_id, ChunkTerm.term, ChunkTerm.tf, Chunk.token_count)
        .join(Chunk, Chunk.id == ChunkTerm.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.is_current.is_(True))
        .where(Document.deleted_at.is_(None))
        .where(Document.audience == audience)
        .where(ChunkTerm.term.in_(query_terms))
    )
    if categories:
        statement = statement.where(Document.category.in_(categories))
    grouped: dict[str, tuple[dict[str, int], int]] = {}
    for chunk_id, term, tf, token_count in session.execute(statement).all():
        bucket = grouped.get(chunk_id)
        if bucket is None:
            grouped[chunk_id] = ({term: int(tf)}, int(token_count))
        else:
            bucket[0][term] = int(tf)
    scored: list[tuple[str, float]] = []
    for chunk_id, (term_map, doc_length) in grouped.items():
        value = score_terms(
            term_map,
            doc_length=doc_length,
            avgdl=stats.avgdl,
            n_docs=stats.n_docs,
            document_frequencies=frequencies,
            query_terms=query_terms,
            k1=k1,
            b=b,
        )
        if value > 0:
            scored.append((chunk_id, value))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:limit]


def term_counts(text: str) -> tuple[Counter[str], int]:
    tokens = tokenize(text)
    return Counter(tokens), len(tokens)
