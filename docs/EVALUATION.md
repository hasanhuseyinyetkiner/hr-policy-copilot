# Evaluation — HR Policy Copilot

Honest measurement of retrieval and answering behavior on the **seeded synthetic** policy corpus. This is not a legal-advice quality study and **not** a held-out production leaderboard.

## Two kinds of runs (do not conflate)

| Kind | Embedder | Artifact | What it proves |
| --- | --- | --- | --- |
| **Fixture validation** | Deterministic `hash` | [`EVAL.md`](EVAL.md) / [`EVAL_RESULTS.json`](EVAL_RESULTS.json) | Harness + seed labels + evidence/citation path work; safe for CI-style local checks |
| **MiniLM-on-seed** | Local `all-MiniLM-L6-v2` | [`EVAL_MINILM.md`](EVAL_MINILM.md) / [`EVAL_RESULTS_MINILM.json`](EVAL_RESULTS_MINILM.json) | Same n=11 labels with the **demo** dense model; still the tiny synthetic corpus |
| **Held-out / production study** | — | **Not in repo** | Would need larger labeled set, calibration, env disclosure — **do not invent** |

Perfect or near-perfect scores on **n=11** synthetic questions are **expected** for both hash and MiniLM-on-seed. They must not be marketed as proof that hybrid beats dense in production HR retrieval.

## What is measured

| Metric | Definition in this repo |
| --- | --- |
| Recall@4 | Gold document title appears among the top-4 used/retrieved passages for answerable items |
| MRR | Reciprocal rank of the first gold hit |
| Citation precision | Cited titles align with expected gold titles for answerable items |
| Faithfulness | `sha256(citation.snippet)` matches the stored chunk text hash (extractive integrity) |
| Abstention accuracy | Correct `abstain` / `ambiguous` behavior on unanswerable rows |

Implementation: `backend/app/eval_metrics.py`. Question set: `data/eval/questions.jsonl` (**n=11**).

## Embedder backends

| Backend | Flag | Used for | Status |
| --- | --- | --- | --- |
| `hash` | `--backend hash` (default) | pytest + fixture scores | Measured — fixture-only |
| `local` MiniLM (`all-MiniLM-L6-v2`) | `--backend local` | Live demo + separate eval files | Measured on seed 2026-10-20 — **not** held-out |
| Sparse-only | `--modes sparse` (any backend) | BM25 ablation / degraded path | Measured on same n=11 |

Hash and MiniLM runs write **different** files so fixture tables are never overwritten by MiniLM (`scripts/run_eval.py`).

## Latest fixture results (hash)

Source: [`EVAL_RESULTS.json`](EVAL_RESULTS.json). Measured `2026-10-20T15:32:20Z`, n=11, `embedding_backend=hash`.

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| sparse | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Latest MiniLM-on-seed results

Source: [`EVAL_RESULTS_MINILM.json`](EVAL_RESULTS_MINILM.json). Measured `2026-10-20T15:33:03Z` on this authoring machine (Windows 11, CPU torch, model under `models/all-MiniLM-L6-v2`, `HF_HUB_OFFLINE=1` in the ephemeral eval app). Same n=11 labels.

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| sparse | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

**Interpretation:** On this demographically tiny seed, hash and MiniLM do not separate modes. That is a **corpus/label size limitation**, not evidence that retrieval mode choice is irrelevant at scale.

## Question mix

| Expect | Count | Examples |
| --- | --- | --- |
| `answer` | 6 | Leave days, sick leave, training window, meals, reviews, notice |
| `conflict` | 1 | In-office days (Remote Work vs Field Exception) |
| `abstain` | 3 | Iguanas, pension matching, parking garage |
| `ambiguous` | 1 | “General vibe” |

## Reproduce

```powershell
# Fixture (hash) — default; writes EVAL.md + EVAL_RESULTS.json
cd backend
uv run python ../scripts/run_eval.py

# MiniLM-on-seed — writes EVAL_MINILM.md + EVAL_RESULTS_MINILM.json only
uv run python -m app.download_model   # if needed
uv run python ../scripts/run_eval.py --backend local
```

## Automated tests (correctness, not leaderboard)

Beyond the fixture metrics, the suite covers extractive equality, abstention, conflict + superseded hiding, citation survival after replace, BM25 corpus sharing across two app instances, hostile uploads, sparse fallback, and `/health` under ingest load. See README Testing section for the latest locally verified `pytest` count.

## Known evaluation gaps

1. **No held-out / larger-corpus hybrid-vs-dense study** — MiniLM-on-seed is still n=11 synthetic; do not treat it as production RAG quality.
2. Thresholds (`evidence_min_*`) are hand-set for the demo seed, not calibrated on a labeled train/dev split.
3. Contradiction detection is specialized (office-day claims), not a general NLI model.
4. Audience is a retrieval filter in the MVP, not an authorization evaluation.
