# Frontend — HR Policy Copilot

React + Vite + TypeScript UI for the evidence-first HR policy assistant. Talks to the FastAPI backend on loopback (`127.0.0.1:8101`) via the Vite dev proxy.

## Architecture

| Piece | Role |
| --- | --- |
| React 19 + React Router | Pages: Overview, Ask, Library, Versions, Source, Settings |
| TanStack Query | Server state for overview, documents, conversations, readiness |
| Tailwind CSS v4 | Layout and theming (light/dark via CSS variables) |
| Vite | Dev server `5101`, production build to `dist/` |

```text
src/
  api.ts              Typed fetch helpers → /api, /health, /ready
  types.ts            Shared DTO shapes
  App.tsx             Route table inside Shell
  components/
    Shell.tsx         Nav, demo banner, readiness notice
    AnswerPanel.tsx   Quotes, citations, conflict, abstention, inspector
    States.tsx        Loading / empty / error
  pages/
    Overview.tsx      Corpus counts + example prompts
    Ask.tsx           Question → extractive answer flow
    Library.tsx       Upload / list / delete
    Versions.tsx      Document revision history
    Source.tsx        Highlighted cited passage
    Settings.tsx      Reset demo / delete-all / status
```

Backend integration: Vite proxies `/api`, `/health`, and `/ready` to `http://127.0.0.1:8101` (`vite.config.ts`). Production Compose serves the built static assets behind the same API origin pattern.

## Environment and startup

No frontend-specific secrets. Backend env lives in the repo root [`.env.example`](../.env.example).

```powershell
# Terminal 1 — API (from repo)
cd backend
uv sync
uv run python -m app.download_model   # first time, for MiniLM demo
uv run python -m app

# Terminal 2 — UI
cd frontend
pnpm install
pnpm dev
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:5101 | Web UI |
| http://127.0.0.1:8101/docs | OpenAPI |
| http://127.0.0.1:8101/ready | Readiness (`ok` / `degraded`) |

Empty library: use **Settings → Reset demo** or set `SEED_ON_STARTUP=true` on the API.

## Screens and components

- **Ask / AnswerPanel** — extractive quotes with citation chips; “Sources disagree” when current policies conflict; abstention when evidence fails; optional retrieval inspector (BM25 / dense / RRF).
- **Library** — PDF / DOCX / TXT / HTML upload; indexing state; delete.
- **Source viewer** — jump from a citation to the highlighted chunk for that `document_version_id`.
- **Settings** — model / retrieval status, demo reset, delete-all; persistent “Local demo · synthetic data” when `APP_ENV=demo`.

`Audience` (`staff` / `exec`) is a **retrieval filter** exposed in the UI — not authentication or authorization. There is no login in the MVP.

## Screenshots

Authentic captures from a local run live in [`docs/screenshots/`](../docs/screenshots/) (light/dark pairs for answer, abstain, source, library). Regenerate:

```powershell
pnpm screenshots
```

Requires API + model available as configured in `playwright.config.ts` (ports `8101` / `5101`).

## Testing

```powershell
pnpm lint
pnpm typecheck
pnpm test          # Vitest (AnswerPanel unit smoke)
pnpm build
pnpm e2e           # Playwright: seeded ask + upload→index→cite
```

CI runs lint, `tsc`, Vitest, and build (see [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)). Playwright e2e/screenshots are local/demo capture steps, not the CI frontend job.

## Related docs

- Root [README](../README.md) — product overview, scope, limitations
- [Architecture](../docs/ARCHITECTURE.md) — end-to-end topology
- [Evaluation](../docs/EVALUATION.md) — labeled retrieval metrics
