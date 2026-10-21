# Evaluation — HR Policy Copilot

Labeled retrieval checks on the **seeded synthetic** corpus (`data/eval/questions.jsonl`, **n=11**). Not a held-out production leaderboard.

## Runs

| Kind | Embedder | Artifact | What it proves |
| --- | --- | --- | --- |
| Fixture | Deterministic `hash` | [`EVAL_RESULTS.json`](EVAL_RESULTS.json) | Harness + seed labels + citation path |
| MiniLM-on-seed | Local `all-MiniLM-L6-v2` | [`EVAL_RESULTS_MINILM.json`](EVAL_RESULTS_MINILM.json) | Same n=11 with the demo dense model |
| Held-out study | — | **Not in repo** | Do not invent |

Near-perfect scores on n=11 synthetic questions are expected. They do not prove hybrid beats dense on real HR corpora.

## Metrics

| Metric | Definition |
| --- | --- |
| Recall@4 | Gold document title in top-4 citations (answerable/conflict) |
| MRR | Reciprocal rank of first gold title |
| Citation precision | Cited titles ⊆ gold titles (answerable) |
| Faithfulness | `sha256(citation.snippet)` matches stored hash |
| Abstention accuracy | Correct abstain on abstain/ambiguous rows |

Implementation: `backend/app/eval_metrics.py`. Modes via `retrieval_preference`: `hybrid` | `dense` | `sparse`.

## Hash fixture results

Measured `2026-10-20T15:32:20Z`, n=11, `embedding_backend=hash`.

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| sparse | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## MiniLM-on-seed results

Measured `2026-10-20T15:33:03Z`, same n=11 labels, local MiniLM under `models/`.

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| sparse | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

On this tiny seed, modes do not separate — a corpus-size limit, not a hybrid≫dense proof.

## Question mix

| Expect | Count | Examples |
| --- | --- | --- |
| `answer` | 6 | Leave days, sick leave, training window, meals, reviews, notice |
| `conflict` | 1 | In-office days (Remote Work vs Field Exception) |
| `abstain` | 3 | Iguanas, pension matching, parking garage |
| `ambiguous` | 1 | “General vibe” |

## Reproduce

```powershell
cd backend
uv run python ../scripts/run_eval.py
uv run python -m app.download_model   # if needed
uv run python ../scripts/run_eval.py --backend local
```

## Gaps

1. No held-out / larger-corpus hybrid-vs-dense study.
2. Evidence thresholds are hand-set for the demo seed.
3. Contradiction detection covers office-day claims only.
4. Audience is a retrieval filter, not authorization.
