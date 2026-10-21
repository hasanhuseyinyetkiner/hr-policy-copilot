"""Reciprocal rank fusion."""

from __future__ import annotations


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for index, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + index)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def rrf_list_contributions(
    rankings: list[list[str]],
    *,
    k: int = 60,
) -> dict[str, list[float]]:
    """Per-item contribution from each ranking list (same terms as RRF).

    ``contributions[item_id][i]`` is ``1/(k+rank)`` from ``rankings[i]``, or ``0.0``
    when the item is absent from that list.
    """
    contributions: dict[str, list[float]] = {}
    n_lists = len(rankings)
    for list_index, ranking in enumerate(rankings):
        for index, item_id in enumerate(ranking, start=1):
            bucket = contributions.setdefault(item_id, [0.0] * n_lists)
            bucket[list_index] = 1.0 / (k + index)
    return contributions
