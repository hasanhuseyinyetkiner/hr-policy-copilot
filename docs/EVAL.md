# Evaluation results (hash fixture)

Measured on the seeded synthetic corpus (`data/eval/questions.jsonl`), **n=11** questions.
Embedding backend for this run: `hash`.
Measured at (UTC): `2026-10-20T15:32:20Z`.

## What this table is (and is not)

| This run | Not this run |
| --- | --- |
| Fixture / labeled validation on n=11 synthetic rows | A claim that hybrid beats dense on real HR corpora |
| Deterministic **hash** embedder (unit-test stand-in) | Live `all-MiniLM-L6-v2` quality on held-out corpora |
| Expected near-perfect scores on a tiny synthetic set | Held-out production leaderboard |

For the **separate** MiniLM-on-seed run (same n=11 labels, different embedder), see [`EVAL_MINILM.md`](EVAL_MINILM.md). Narrative and gaps: [`EVALUATION.md`](EVALUATION.md).

## Methodology (short)

| Metric | Definition |
| --- | --- |
| Recall@4 | Gold title in top-4 citations (answerable/conflict) |
| MRR | Reciprocal rank of first gold title |
| Citation precision | Cited titles ⊆ gold titles (answerable) |
| Faithfulness | `sha256(citation.snippet)` matches stored hash |
| Abstention accuracy | Correct abstain on abstain/ambiguous |

Modes via `retrieval_preference`: `hybrid` = BM25 + dense + RRF; `dense` = dense-only; `sparse` = BM25-only.

Implementation: `backend/app/eval_metrics.py`. Runner: `scripts/run_eval.py`.

## Results

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| sparse | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Breakdown: 7 answerable/conflict items, 4 abstain+ambiguous; `answer_hits=7`, `abstain_correct=4/4` for each mode. Raw JSON: [`EVAL_RESULTS.json`](EVAL_RESULTS.json).

## Reproduce

```powershell
cd backend
uv run python ../scripts/run_eval.py
# equivalent: --backend hash --modes hybrid,dense,sparse
```

MiniLM (writes separate files; does not overwrite this table):

```powershell
cd backend
uv run python -m app.download_model   # if models/ missing
uv run python ../scripts/run_eval.py --backend local
```
