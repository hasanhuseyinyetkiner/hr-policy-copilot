"""Evaluation metrics for the seeded HR policy corpus.

Method (documented for README / docs/EVALUATION.md):
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
- Modes via ``retrieval_preference``: hybrid | dense | sparse.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import REPO_ROOT

DEFAULT_EVAL_PATH = REPO_ROOT / "data" / "eval" / "questions.jsonl"
HELDOUT_V1_PATH = REPO_ROOT / "data" / "eval" / "heldout" / "v1" / "questions.jsonl"
K = 4


def resolve_eval_path(dataset: str) -> Path:
    """Map dataset id to JSONL path. Held-out sets must stay separate from the seed fixture."""
    key = dataset.strip().lower()
    if key in {"seed", "fixture", "questions", "default"}:
        return DEFAULT_EVAL_PATH
    if key in {"heldout", "heldout/v1", "heldout-v1", "v1"}:
        return HELDOUT_V1_PATH
    candidate = REPO_ROOT / "data" / "eval" / dataset / "questions.jsonl"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Unknown eval dataset: {dataset}")


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


def category_breakdown(
    client: TestClient,
    rows: list[dict[str, Any]],
    *,
    preference: str = "hybrid",
) -> dict[str, dict[str, Any]]:
    """Per-category hit/miss counts for held-out reporting (does not change thresholds)."""
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        category = str(row.get("category") or row.get("expect") or "uncategorized")
        bucket = buckets.setdefault(category, {"n": 0, "correct": 0})
        bucket["n"] += 1
        body = _query(client, row["question"], preference)
        citations = body.get("citations") or []
        gold = set(row.get("titles") or [])
        expect = row["expect"]
        if expect in {"abstain", "ambiguous"}:
            ok = body.get("mode") == "abstain" and not citations
        else:
            titles = {item["document_title"] for item in citations}
            ok = bool(gold & titles)
            snippet = row.get("snippet") or ""
            if snippet and not any(snippet in item.get("snippet", "") for item in citations):
                ok = False
        if ok:
            bucket["correct"] += 1
    return {
        key: {
            "n": value["n"],
            "correct": value["correct"],
            "accuracy": (value["correct"] / value["n"]) if value["n"] else 0.0,
        }
        for key, value in sorted(buckets.items())
    }


def evaluate_all(
    client: TestClient,
    rows: list[dict[str, Any]] | None = None,
    *,
    modes: tuple[str, ...] = ("hybrid", "dense", "sparse"),
    k: int = K,
    embedding_backend: str = "hash",
    question_set: str = "data/eval/questions.jsonl",
    dataset_id: str = "seed",
    include_category_breakdown: bool = False,
) -> dict[str, Any]:
    dataset = rows if rows is not None else load_eval_rows()
    by_mode = {
        mode: asdict(evaluate_mode(client, dataset, preference=mode, k=k)) for mode in modes
    }
    backend_note = (
        "Default runner uses the deterministic hash embedder (see scripts/run_eval.py)."
        if embedding_backend == "hash"
        else (
            "This run used the local MiniLM embedder (`sentence-transformers/all-MiniLM-L6-v2`) "
            "via embedding_backend=local (see scripts/run_eval.py --backend local)."
        )
    )
    heldout = dataset_id.startswith("heldout")
    sample = next(iter(by_mode.values()), None)
    report: dict[str, Any] = {
        "k": k,
        "n_questions": len(dataset),
        "embedding_backend": embedding_backend,
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": "seeded synthetic Northwind People policies (data/demo)",
        "dataset_id": dataset_id,
        "question_set": question_set,
        "held_out": heldout,
        "leak_policy": (
            "Held-out labels must not be used to tune evidence thresholds or retrieval params."
            if heldout
            else "Seed fixture may be used for wiring checks; not a production leaderboard."
        ),
        "method": (
            "Recall@K / MRR / citation precision on seeded synthetic policies; "
            "faithfulness = sha256(snippet) match; abstention accuracy on "
            "unanswerable/ambiguous/superseded-heldout items; modes via retrieval_preference "
            f"(hybrid|dense|sparse). {backend_note}"
        ),
        "modes": by_mode,
        "breakdown": {
            "answer_hits": sample["answer_hits"] if sample else 0,
            "n_answerable": sample["n_answerable"] if sample else 0,
            "abstain_correct": sample["abstain_correct"] if sample else 0,
            "abstain_total": sample["abstain_total"] if sample else 0,
        },
    }
    if include_category_breakdown or heldout:
        primary = modes[0] if modes else "hybrid"
        report["category_breakdown"] = {
            primary: category_breakdown(client, dataset, preference=primary)
        }
    return report


def format_markdown(report: dict[str, Any]) -> str:
    """Render a console/results table (JSON is written to docs/; narrative in EVALUATION.md)."""
    n = report.get("n_questions", "?")
    backend = report.get("embedding_backend", "unknown")
    measured = report.get("measured_at")
    question_set = report.get("question_set", "data/eval/questions.jsonl")
    dataset_id = report.get("dataset_id", "seed")
    heldout = bool(report.get("held_out"))
    is_hash = backend == "hash"
    if heldout:
        title = (
            "# Held-out evaluation results (hash)"
            if is_hash
            else "# Held-out evaluation results (local MiniLM)"
        )
        raw_name = (
            "EVAL_RESULTS_HELDOUT_V1.json"
            if is_hash
            else "EVAL_RESULTS_HELDOUT_V1_MINILM.json"
        )
    else:
        title = (
            "# Evaluation results (hash fixture)"
            if is_hash
            else "# Evaluation results (local MiniLM)"
        )
        raw_name = "EVAL_RESULTS.json" if is_hash else "EVAL_RESULTS_MINILM.json"
    other = (
        "Update [`EVALUATION.md`](EVALUATION.md) if these scores change."
    )
    caveat_row = (
        (
            "Deterministic **hash** embedder (unit-test stand-in)",
            "Live `all-MiniLM-L6-v2` quality on held-out corpora",
        )
        if is_hash
        else (
            "Labeled synthetic MiniLM run on the demo seed",
            "Production RAG leaderboard",
        )
    )
    lines = [
        title,
        "",
        f"Dataset `{dataset_id}` (`{question_set}`), **n={n}** questions.",
        f"Embedding backend for this run: `{backend}`.",
    ]
    if heldout:
        lines.append(
            "Held-out set: **do not** tune evidence thresholds or retrieval params from these scores."
        )
    if measured:
        lines.append(f"Measured at (UTC): `{measured}`.")
    lines.extend(
        [
            "",
            "## What this table is (and is not)",
            "",
            "| This run | Not this run |",
            "| --- | --- |",
            "| Fixture / labeled validation on n=11 synthetic rows "
            "| A claim that hybrid beats dense on real HR corpora |",
            f"| {caveat_row[0]} | {caveat_row[1]} |",
            "| Expected near-perfect scores on a tiny synthetic set "
            "| Held-out production leaderboard |",
            "",
            f"{other} Narrative and gaps: [`EVALUATION.md`](EVALUATION.md).",
            "",
            "## Methodology (short)",
            "",
            "| Metric | Definition |",
            "| --- | --- |",
            "| Recall@4 | Gold title in top-4 citations (answerable/conflict) |",
            "| MRR | Reciprocal rank of first gold title |",
            "| Citation precision | Cited titles ⊆ gold titles (answerable) |",
            "| Faithfulness | `sha256(citation.snippet)` matches stored hash |",
            "| Abstention accuracy | Correct abstain on abstain/ambiguous |",
            "",
            "Modes via `retrieval_preference`: `hybrid` = BM25 + dense + RRF; "
            "`dense` = dense-only; `sparse` = BM25-only.",
            "",
            "Implementation: `backend/app/eval_metrics.py`. "
            "Runner: `scripts/run_eval.py`.",
            "",
            "## Results",
            "",
            (
                f"| Mode | Recall@{report['k']} | MRR | Citation precision "
                "| Faithfulness | Abstention accuracy |"
            ),
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
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
    sample = next(iter(report["modes"].values()), None)
    if sample:
        lines.append("")
        lines.append(
            f"Breakdown: {sample['n_answerable']} answerable/conflict items, "
            f"{sample['abstain_total']} abstain+ambiguous; "
            f"`answer_hits={sample['answer_hits']}`, "
            f"`abstain_correct={sample['abstain_correct']}/{sample['abstain_total']}` "
            f"for each mode. Raw JSON: [`{raw_name}`]({raw_name})."
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```powershell",
            "cd backend",
        ]
    )
    if is_hash:
        lines.extend(
            [
                "uv run python ../scripts/run_eval.py",
                "# equivalent: --backend hash --modes hybrid,dense,sparse",
                "```",
                "",
                "MiniLM (writes separate files; does not overwrite this table):",
                "",
                "```powershell",
                "cd backend",
                "uv run python -m app.download_model   # if models/ missing",
                "uv run python ../scripts/run_eval.py --backend local",
                "```",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "uv run python -m app.download_model   # if models/ missing",
                "uv run python ../scripts/run_eval.py --backend local --modes hybrid,dense,sparse",
                "```",
                "",
                "If the model directory is missing, the runner exits without inventing scores.",
                "",
            ]
        )
    return "\n".join(lines)
