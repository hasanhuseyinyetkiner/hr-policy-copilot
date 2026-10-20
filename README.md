# HR Policy Copilot

Ask HR policy questions. Get answers you can verify.

Local demo with **hybrid retrieval** (BM25 + dense + RRF), versioned synthetic HR policies, and extractive citations. No paid API keys required.

## Verified local run (Windows)

```powershell
# Terminal 1 — API (127.0.0.1:8101)
cd backend
uv sync
uv run python -m app

# Terminal 2 — Web (127.0.0.1:5101)
cd frontend
pnpm install
pnpm dev
```

| Service | URL |
| --- | --- |
| Web | http://127.0.0.1:5101 |
| API docs | http://127.0.0.1:8101/docs |
| Health | http://127.0.0.1:8101/health |

Demo data seeds on startup (synthetic policies). First boot downloads/loads `all-MiniLM-L6-v2` from `models/` (already present after `scripts/download_models.py`).

```powershell
# Backend tests (verified)
cd backend
uv run pytest -q
```

## Status

Backend + frontend MVP runnable. Docker Compose / PostgreSQL path is for CI only (no Docker on the authoring machine). License pending owner decision.
