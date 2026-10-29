# Evaluation — HR Policy Copilot

> **Status update (2026-10-29):** The formerly held-out v1 set is now a development regression set: its known revision failures informed the version-scope guard. No retrieval or evidence thresholds were tuned on it. Earlier held-out results below are historical, not an independent assessment of the current implementation.

## Revision guard: before and after

On the same SQLite/Qdrant-local synthetic corpus, hash embeddings, and 12 questions, the [before](EVAL_RESULTS_REVISION_BEFORE.json) and [after](EVAL_RESULTS_REVISION_AFTER.json) runs gave identical results across hybrid, dense, and sparse modes: Recall@4 6/7 both times; abstention accuracy 3/5 → 4/5; superseded category 0/2 → 1/2. The remaining failure asks whether a claim appears in a current policy: retrieval overlap cannot establish that the claim is true. One paraphrase remains missed. The guard abstains for explicit numbered or historical versions, including numbered current versions; it does not perform historical search. This comparison is a regression check, not an unbiased estimate of generalization.

A hash match only checks snapshot integrity, not whether a quotation answers the question. Title-based citation metrics likewise do not measure answer correctness.

## External corpus feasibility

GitLab's [public handbook](https://handbook.gitlab.com/handbook/about/direction/) is a plausible real-world source. The handbook's [usage page](https://handbook.gitlab.com/handbook/about/handbook-usage/) identifies CC BY-SA 4.0 for external use, while its [repository licence at a pinned revision](https://gitlab.com/gitlab-com/content-sites/handbook/-/raw/26b13579f16d5ec5dc4dbecb42929a1b2c26b057/LICENCE) describes MIT terms for software and associated documentation. Individual pages can carry their own terms, such as the [event code of conduct](https://gitlab.com/gitlab-com/content-sites/handbook/-/blob/228e22856732c6dd6c5ec83ed68b442681b76ce0/content/handbook/company/culture/ecoc.md), which identifies CC0 and third-party influences. These sources do not establish a single verified license for every prospective HR page. A defensible corpus needs page-level provenance and terms, a pinned snapshot, careful HTML/Markdown conversion, independently authored questions and adjudicated passage-level labels. No real-corpus experiment was run, and no external quality claim is made.


Labeled retrieval checks on the **seeded synthetic** corpus. Two datasets:

| Dataset | Path | Role |
| --- | --- | --- |
| Seed / fixture | `data/eval/questions.jsonl` (n=11) | Wiring + citation path; may appear in CI pytest |
| Held-out v1 | `data/eval/heldout/v1/questions.jsonl` (n=12) | Separate labels (exact / paraphrase / negation / unanswerable / superseded). Formerly held out; now development regression data. Do not tune thresholds from this set. |

Neither is a production leaderboard.

## Runs

| Kind | Embedder | Artifact | What it proves |
| --- | --- | --- | --- |
| Fixture | Deterministic `hash` | [`EVAL_RESULTS.json`](EVAL_RESULTS.json) | Harness + seed labels + citation path |
| MiniLM-on-seed | Local `all-MiniLM-L6-v2` | [`EVAL_RESULTS_MINILM.json`](EVAL_RESULTS_MINILM.json) | Same n=11 with the demo dense model |
| Formerly held-out v1 | `hash` / `local` | [`EVAL_RESULTS_HELDOUT_V1.json`](EVAL_RESULTS_HELDOUT_V1.json) | Historical artifact; current development regression runs are written separately as `EVAL_RESULTS_DEVELOPMENT_V1.json` |

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

## Formerly held-out v1 (historical baseline)

```powershell
cd backend
uv run python ../scripts/run_eval.py --dataset heldout/v1
uv run python ../scripts/run_eval.py --dataset heldout/v1 --backend local
```

Manifest: [`../data/eval/heldout/v1/manifest.json`](../data/eval/heldout/v1/manifest.json).

### Historical hash results before the guard

Measured `2026-10-21T13:09:55Z`, n=12, `embedding_backend=hash`. Raw: [`EVAL_RESULTS_HELDOUT_V1.json`](EVAL_RESULTS_HELDOUT_V1.json).

| Mode | Recall@4 | MRR | Citation precision | Faithfulness | Abstention accuracy |
| --- | --- | --- | --- | --- | --- |
| hybrid | 0.86 | 0.93 | 0.93 | 1.00 | 0.60 |
| dense | 0.86 | 0.93 | 0.93 | 1.00 | 0.60 |
| sparse | 0.86 | 0.93 | 0.93 | 1.00 | 0.60 |

Category breakdown (hybrid): exact 2/2 · paraphrase 2/3 · negation 2/2 · unanswerable 3/3 · superseded 0/2.

Honest reading: seed fixture perfection does **not** transfer. Before the guard, superseded / revision-scoped questions attracted current-policy citations. One paraphrase miss. **Do not** lower evidence thresholds to chase these scores.

## Latency baseline

See [`PERFORMANCE_BASELINE.md`](PERFORMANCE_BASELINE.md) (regenerated by `scripts/measure_latency.py`). Latest local MiniLM hybrid mean on the seed question set is recorded there — machine-specific, not an SLA.

## Gaps

1. Held-out v1 is still the same tiny synthetic corpus (harder wording, not enterprise scale).
2. Evidence thresholds are hand-set for the demo seed (must not be fit on held-out).
3. Contradiction detection covers office-day claims only.
4. Audience is a retrieval filter, not authorization.
5. Historical intent detection is heuristic; current claim verification still fails on one revision-related item.
