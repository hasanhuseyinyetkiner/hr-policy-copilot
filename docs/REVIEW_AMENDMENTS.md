# Design review amendments (binding)

These amendments come from the pre-implementation design review (2026-10-20). They **override** any conflicting text in `docs/PRODUCT_SPEC.md`. IDs refer to review findings.

## Environment and delivery (all products)

- **[C-1] No Docker, no local PostgreSQL.** The dev machine is Windows 11 with `uv` (use Python 3.12: `uv python pin 3.12`), Node 24 and pnpm. Provide a **native dev path that is verified locally** (`uv run ...` backend, `pnpm dev` frontend). Local tests may use SQLite through the same SQLAlchemy models; PostgreSQL-only behavior gets a SQLite-safe fallback or a `@pytest.mark.postgres` marker that runs in CI. Write `compose.yaml` and Dockerfiles, but they are verified **only in CI** by a `compose-smoke` job; the README must say so until that job passes.
- **CI** (GitHub Actions, `ubuntu-latest`): backend Ruff + pytest against a PostgreSQL service container; frontend ESLint + `tsc` + Vitest + build; `compose-smoke` (`docker compose up --build -d`, wait for `/ready`, then `docker compose down -v`).
- **[C-6] Ports:** API `8101`, web `5101`, PostgreSQL host port `5401`, Qdrant host port `6301`.
- **[C-2] Loopback by default.** Uvicorn binds `127.0.0.1`; Compose port mappings use `127.0.0.1:` prefixes. No auth in the MVP, so startup refuses a non-loopback host unless `ALLOW_NETWORK_BIND=true` is set explicitly. `APP_ENV=demo` shows a persistent "Local demo · synthetic data" banner.
- **[C-3] No CPU-heavy work on the event loop.** Embedding, parsing and scoring run via `run_in_threadpool` or a process pool. Long jobs are persisted rows with `status` and `heartbeat_at`; a startup reaper marks stale `RUNNING` jobs `FAILED` with a reason. Add a test proving `/health` stays responsive while a job runs.
- **[C-4] Licensing and git.** Do **not** add a `LICENSE` file; the README states "License: pending owner decision". Do not create remotes or push. Commit locally in small conventional commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `ci:`).
- **[C-5] CPU-only torch.** Pin torch to `https://download.pytorch.org/whl/cpu` through an explicit `[[tool.uv.index]]` so no `nvidia-*` packages are resolved.
- **Brand:** accent color `#0D9488` (teal). Light and dark themes.

## Product-specific

- **[HR-1] PostgreSQL is the source of truth.** Every dense or sparse hit is post-filtered against PostgreSQL (`chunk.is_current`, category and permission filters) before it can be shown or cited. Provide `scripts/reconcile_index.py`. Fault-injection test: raise after the PG commit and before the vector delete; no superseded chunk may be returned.
- **[HR-2] No unversioned per-process BM25.** Preferred: BM25 computed from term statistics persisted in the database (or PostgreSQL full-text search with an SQLite FTS5 fallback). If `rank-bm25` is used, key the in-memory index to a `corpus_version` stored in the database and rebuild when it changes. Test with two app instances against one database.
- **[HR-3] Hostile uploads.** `pypdf>=6.20.1` (fixes GHSA-9mx8-4j7g-633p, GHSA-qfv9-64jg-mh7p, CVE-2026-84309, CVE-2026-59936). Parse in a subprocess with a timeout (default 20 s), page cap and extracted-size cap. Reject DOCX whose total uncompressed size exceeds 50 MB or whose compression ratio exceeds 100. Tests: a PDF with an unterminated inline image (`BI ... ID` without `EI`) and a zip-bomb DOCX must both end `FAILED` within the timeout.
- **[HR-4] Citations survive replacement.** Chunks are soft-deleted (`superseded_at`); only their vectors are removed. `Citation` stores snippet text, its sha256 and `document_version_id`. Test: ask, replace the document, reopen the old conversation; the citation still shows the old version's text and revision.
- **[HR-5] Honest offline mode.** Use `sentence-transformers/all-MiniLM-L6-v2` (verify its license), downloaded by an explicit `make models` / script into a gitignored cache; runtime honors `HF_HUB_OFFLINE=1`. If the model or Qdrant is unavailable, `/ready` reports `degraded` with a reason and queries fall back to sparse-only retrieval with a visible UI notice. Local dev uses Qdrant local mode (`QdrantClient(path=...)`, single process only); Compose uses the Qdrant server.
