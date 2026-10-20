# Security, privacy, and limitations — HR Policy Copilot

Honest scope for a **local demo** that answers questions from **synthetic** HR policies. This document does not claim production hardening, compliance certification, or legal advice capability.

## Intended threat model (demo)

| In scope for MVP hardening | Out of scope |
| --- | --- |
| Loopback bind by default | Multi-user authentication / SSO |
| Hostile PDF/DOCX parse sandbox | Network-exposed multi-tenant SaaS |
| Upload size / extension caps | Enterprise DLP or eDiscovery |
| Citations that cannot invent text | Guaranteeing policy completeness |
| No automatic employment decisions | Regulatory certification (SOC2, ISO, etc.) |

## Network and access

- Uvicorn defaults to `127.0.0.1`. Non-loopback hosts require explicit `ALLOW_NETWORK_BIND=true` ([C-2](REVIEW_AMENDMENTS.md)).
- Compose publishes ports only on `127.0.0.1` (API `8101`, web `5101`, Postgres `5401`, Qdrant `6301`).
- **No authentication** in the MVP. Anyone who can reach the bind address can query and mutate the library.
- `Audience` (`staff` / `exec`) is a **retrieval filter**, not access control. Do not treat it as authorization.

## Document handling

- Uploads: max bytes (`upload_max_bytes`), allowed extensions, random storage names under `UPLOAD_DIR`.
- Parse in a **subprocess** with timeout, page cap, and extracted-text cap.
- DOCX zip-bomb checks: uncompressed size and compression-ratio caps.
- Pathological PDF: unterminated inline image rejected.
- `pypdf` pinned per advisory list in [REVIEW_AMENDMENTS.md](REVIEW_AMENDMENTS.md) HR-3.
- HTML seed/path strips script content (covered by tests).

## Answer integrity (trustworthy AI boundary)

- Answers are **extractive quotes** from indexed text, not free-form model generations (LLM grounding is roadmap-only and unwired).
- Evidence thresholds force **abstention** when overlap/score gates fail.
- Conflicting current policies are shown together; the system does not silently pick one.
- Citation rows store snippet + sha256 + version id so replacement cannot rewrite history unnoticed.

## Privacy and HR sensitivity

- Demo corpus is **synthetic** (Northwind People). Do not upload real employee personal data into this MVP.
- Persistent UI banner when `APP_ENV=demo`: “Local demo · synthetic data.”
- Footer/preamble: not legal advice.
- No automated hire/reject/discipline actions are implemented — and must not be added without human-review design.

## Operational failure modes

- Missing MiniLM or Qdrant → `/ready` degraded, sparse-only answers with UI notice (not silent invent).
- Stale ingest jobs reaped to `FAILED` on startup.
- Security response headers set in FastAPI middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`.

## Secrets and artifacts

- Do not commit `.env`, real policy PDFs with PII, model caches under `models/`, or upload dumps.
- `.env.example` documents safe local defaults only.

## Claims verified against code (demo MVP)

| Claim | Code / test anchor |
| --- | --- |
| Loopback bind unless `ALLOW_NETWORK_BIND` | `config.enforce_loopback` |
| Parse in subprocess with timeout + caps | `parsing/sandbox.py` → `app.parsing.worker` |
| DOCX zip-bomb / unterminated PDF image reject | `parsing/hostile.py`; `test_hostile_uploads_fail_quickly` |
| DB post-filter before cite | `retrieval.post_filter_chunks`; HR-1 tests |
| Citation snapshots survive replace | `Citation` snippet + sha256 + version; `test_citation_survives_replacement` |
| Abstain when evidence weak | `domain/evidence.py`; answering abstention path |
| Degraded `/ready` + sparse-only | `api.build_ready`; `test_sparse_fallback_when_qdrant_is_down` |
| Audience is not auth | Documented in UI catalog + this file; filter applied in BM25/dense queries only |

## License

License: **pending owner decision** (no `LICENSE` file yet). Do not assume open-source redistribution rights until a license is added. See [`RELEASE_READINESS.md`](RELEASE_READINESS.md).

## Related

- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- Decisions: [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md)
- Binding amendments: [REVIEW_AMENDMENTS.md](REVIEW_AMENDMENTS.md)
- Release blockers: [RELEASE_READINESS.md](RELEASE_READINESS.md)
