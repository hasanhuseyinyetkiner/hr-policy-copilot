"""Evidence gate for extractive answers."""

from dataclasses import dataclass

from app.domain.contradictions import conflicting_office_days, office_day_claims


@dataclass(frozen=True)
class Thresholds:
    min_overlap: int = 3
    min_bm25: float = 1.0
    min_cosine: float = 0.55
    max_passages: int = 4


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: str
    text: str
    overlap: int
    bm25: float
    dense: float | None
    rrf: float
    instruction_override: bool


def passes_threshold(chunk: ScoredChunk, thresholds: Thresholds) -> bool:
    if chunk.instruction_override:
        return False
    if chunk.overlap < thresholds.min_overlap:
        return False
    cosine = chunk.dense or 0.0
    return chunk.bm25 >= thresholds.min_bm25 or cosine >= thresholds.min_cosine


def rejection_reason(chunk: ScoredChunk, thresholds: Thresholds) -> str | None:
    if chunk.instruction_override:
        return "instruction_override"
    if not passes_threshold(chunk, thresholds):
        return "below_evidence_threshold"
    return None


def choose_passages(
    chunks: list[ScoredChunk],
    thresholds: Thresholds,
) -> tuple[list[ScoredChunk], bool]:
    eligible = [chunk for chunk in chunks if passes_threshold(chunk, thresholds)]
    ordered = sorted(eligible, key=lambda chunk: (-chunk.rrf, chunk.chunk_id))
    claims = conflicting_office_days([chunk.text for chunk in ordered])
    contradictory = len(claims) >= 2
    chosen: list[ScoredChunk] = []
    for chunk in ordered:
        keep_for_conflict = contradictory and bool(office_day_claims(chunk.text))
        if len(chosen) < thresholds.max_passages or keep_for_conflict:
            chosen.append(chunk)
        if len(chosen) >= 6:
            break
    return chosen, contradictory
