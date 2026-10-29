# HR Policy Copilot

A local hybrid retrieval and extractive question-answering demo for a synthetic HR policy library. It retrieves passages with BM25 and dense embeddings, combines their ranks, and returns quotations with source snapshots when a heuristic evidence gate passes. It does not generate an explanation or establish that a retrieved passage entails the question.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/answer-dark.png">
  <img src="docs/screenshots/answer-light.png" alt="Demo answer showing conflicting current policy passages" width="100%">
</picture>

## What the measurements show

On 12 synthetic questions using the deterministic hash embedder, a revision-scope guard changed correct abstentions from **3/5 to 4/5**; the two revision-related questions changed from **0/2 to 1/2**. Recall@4 stayed **6/7**. The remaining revision-related false answer asks whether a claim is present in a current policy. A paraphrase also remains missed. Results were the same for hybrid, dense, and sparse in this small run; they do not establish a hybrid advantage. [Before](docs/EVAL_RESULTS_REVISION_BEFORE.json) · [After](docs/EVAL_RESULTS_REVISION_AFTER.json) · [Methods and limitations](docs/EVALUATION.md)

The question set was originally held out, but its known failures informed the fix and it is now development regression data. No evidence or retrieval thresholds were tuned using it. The earlier 11-question seed scores are wiring checks, not evidence of production accuracy. Citation hash checks verify snapshot integrity, not semantic correctness. No external-corpus quality evaluation has been completed; the [GitLab handbook feasibility notes](docs/EVALUATION.md#external-corpus-feasibility) explain the provenance and licensing work still needed.

## How it works

Uploads are parsed into versioned chunks. BM25 and Qdrant dense candidates are filtered against authoritative database rows and fused with reciprocal rank fusion. An overlap and score gate selects passages; citations preserve the exact chunk, version ID and hash. The interface exposes retrieval telemetry and source views. If dense retrieval is unavailable, search falls back to sparse retrieval. See [architecture](docs/ARCHITECTURE.md) and [engineering decisions](docs/ENGINEERING_DECISIONS.md).

Only current versions are searched for answers. Explicit numbered or historical version requests abstain and direct the user to version history, including when the requested number happens to be current. The detector is a limited pattern match and can miss other historical phrasings. Contradiction detection handles the demo's office-day claims only. A retrieved quotation can still be irrelevant or fail to answer the question.

## Run locally

Requires Python 3.12, `uv`, Node.js and `pnpm`. The model download needs network access.

```powershell
cd backend
uv sync
uv run python -m app.download_model
uv run python -m app
```

In another terminal from the repository root:

```powershell
cd frontend
pnpm install
pnpm dev
```

Open [the app](http://127.0.0.1:5101); use **Settings → Reset demo** if the library is empty. [API documentation](http://127.0.0.1:8101/docs) · [Configuration](.env.example) · [Demo recording](docs/assets/demo.gif).

## Verify

```powershell
cd backend
uv run ruff check .
uv run pytest
$env:PYTHONIOENCODING = "utf-8"
uv run python ../scripts/run_eval.py --dataset heldout/v1
```

The evaluation command writes `docs/EVAL_RESULTS_DEVELOPMENT_V1.json`, preserving the historical pre-change result. For frontend checks, run `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` from `frontend`. [CI](.github/workflows/ci.yml) includes additional PostgreSQL and browser checks.

This is a local MVP, not legal advice or a multi-user service. There is no authentication; audience is a retrieval filter, not access control. Do not upload real employee data or expose the demo beyond loopback. Parsing safeguards do not constitute a complete security boundary. See [security](SECURITY.md), [evaluation](docs/EVALUATION.md), [changelog](CHANGELOG.md), and [license](LICENSE).
