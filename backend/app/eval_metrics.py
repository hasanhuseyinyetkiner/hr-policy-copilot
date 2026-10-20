"""Evaluation metrics for the seeded HR policy corpus.

Method (documented for README / EVAL.md):
- Gold labels live in ``data/eval/questions.jsonl``.
- Recall@K: share of non-abstain questions where any gold title appears
  among the top-K citations (K = max_passages, default 4).
- MRR: mean reciprocal rank of the first citation whose title is gold.
- Citation precision: among citations returned for non-abstain questions,
  share whose ``document_title`` is in the gold title set.
- Citation faithfulness: share of citations whose sha256 matches the snippet
  bytes (exact extractive quote).
- Abstention accuracy: share of ``expect=abstain`` / ``expect=ambiguous``
  questions that correctly abstain.
- Dense vs hybrid: same questions with ``retrieval_preference`` dense|hybrid.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import REPO_ROOT

DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "questions.jsonl"
K = 4


@dataclass(frozen=True)
class ModeMetrics:
    mode: str
    n_questions: int
    n_answerable: int
    recall_at_k: float
    mrr: float
    citation_precision: float
    citation_faithfulness: float
    abstention_accuracy: float
    answer_hits: int
    abstain_correct: int
    abstain_total: int


def load_eval_rows(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_EVAL_PATH
    return [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _query(client: TestClient, question: str, preference: str) -> dict[str, Any]:
    response = client.post(
        "/api/query",
        json={"question": question, "retrieval_preference": preference},
    )
    assert response.status_code == 200, response.text
    return response.json()


def evaluate_mode(
    client: TestClient,
    rows: list[dict[str, Any]],
    *,
    preference: str = "hybrid",
    k: int = K,
) -> ModeMetrics:
    reciprocal_ranks: list[float] = []
    answer_hits = 0
    answerable = 0
    citation_relevant = 0
    citation_total = 0
    faithful = 0
    faithful_total = 0
    abstain_correct = 0
    abstain_total = 0

    for row in rows:
        body = _query(client, row["question"], preference)
        citations = body.get("citations") or []
        titles = [item["document_title"] for item in citations[:k]]
        gold = set(row.get("titles") or [])
        expect = row["expect"]

        for citation in citations:
            digest = hashlib.sha256(citation["snippet"].encode("utf-8")).hexdigest()
            faithful_total += 1
            if citation.get("snippet_sha256") == digest:
                faithful += 1

        if expect in {"abstain", "ambiguous"}:
            abstain_total += 1
            if body.get("mode") == "abstain" and not citations:
                abstain_correct += 1
            continue

        answerable += 1
        for title in titles:
            citation_total += 1
            if title in gold:
                citation_relevant += 1

        hit = any(title in gold for title in titles)
        if expect == "conflict":
            hit = hit and gold <= set(titles) and body.get("contradictory") is True
        snippet = row.get("snippet") or ""
        if snippet and not any(snippet in item.get("snippet", "") for item in citations):
            hit = False
        if hit:
            answer_hits += 1
        rank = next(
            (index + 1 for index, title in enumerate(titles) if title in gold),
            None,
        )
        if rank is not None:
            reciprocal_ranks.append(1.0 / rank)

    return ModeMetrics(
        mode=preference,
        n_questions=len(rows),
        n_answerable=answerable,
        recall_at_k=(answer_hits / answerable) if answerable else 0.0,
        mrr=(sum(reciprocal_ranks) / len(reciprocal_ranks)) if reciprocal_ranks else 0.0,
        citation_precision=(citation_relevant / citation_total) if citation_total else 0.0,
        citation_faithfulness=(faithful / faithful_total) if faithful_total else 1.0,
        abstention_accuracy=(abstain_correct / abstain_total) if abstain_total else 1.0,
        answer_hits=answer_hits,
        abstain_correct=abstain_correct,
        abstain_total=abstain_total,
    )


def evaluate_all(
    client: TestClient,
    rows: list[dict[str, Any]] | None = None,
    *,
    modes: tuple[str, ...] = ("hybrid", "dense"),
    k: int = K,
) -> dict[str, Any]:
    dataset = rows if rows is not None else load_eval_rows()
    by_mode = {
        mode: asdict(evaluate_mode(client, dataset, preference=mode, k=k)) for mode in modes
    }
    return {
        "k": k,
        "n_questions": len(dataset),
        "embedding_backend": "hash",
        "method": (
            "Recall@K / MRR / citation precision on seeded synthetic policies; "
            "faithfulness = sha256(snippet) match; abstention accuracy on "
            "unanswerable/ambiguous items; dense vs hybrid via retrieval_preference. "
            "Default runner uses the deterministic hash embedder (see scripts/run_eval.py)."
        ),
        "modes": by_mode,
    }


def format_markdown(report: dict[str, Any]) -> str:
    n = report.get("n_questions", "?")
    backend = report.get("embedding_backend", "unknown")
    lines = [
        "# Evaluation results",
        "",
        f"Measured on the seeded synthetic corpus (`data/eval/questions.jsonl`), "
        f"**n={n}** questions.",
        f"Embedding backend for this run: `{backend}`. "
        "Do not treat these as legal advice or a production MiniLM benchmark.",
        "",
        f"**Method:** {report['method']}",
        "",
        f"| Mode | Recall@{report['k']} | MRR | Citation precision | Faithfulness | Abstention accuracy |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for mode, metrics in report["modes"].items():
        lines.append(
            "| {mode} | {recall:.2f} | {mrr:.2f} | {prec:.2f} | {faith:.2f} | {abs_acc:.2f} |".format(
                mode=mode,
                recall=metrics["recall_at_k"],
                mrr=metrics["mrr"],
                prec=metrics["citation_precision"],
                faith=metrics["citation_faithfulness"],
                abs_acc=metrics["abstention_accuracy"],
            )
        )
    lines.append("")
    return "\n".join(lines)
