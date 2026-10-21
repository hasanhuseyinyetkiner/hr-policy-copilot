# Security — HR Policy Copilot

Honest scope for a **local demo** that answers questions from **synthetic** HR policies. This is not production hardening, compliance certification, or legal advice.

## Demo boundary (loopback-only)

| Rule | Detail |
| --- | --- |
| Bind default | API binds to `127.0.0.1` (`API_HOST`). Startup refuses non-loopback hosts unless `ALLOW_NETWORK_BIND=true` (`config.enforce_loopback`). |
| Compose ports | Published only on `127.0.0.1` (API `8101`, web `5101`, Postgres `5401`, Qdrant `6301`). |
| Auth | **None** in the MVP. Anyone who can reach the bind address can query and mutate the library. |
| Audience filter | `staff` / `exec` is a **retrieval filter**, not access control. |
| Data | Demo corpus is synthetic (Northwind People / POL-SEC-*). Do not upload real employee PII. |
| Network exposure | Do not expose this MVP beyond loopback. Treat `ALLOW_NETWORK_BIND=true` as an explicit break-glass for Compose/CI only. |

## Intended threat model (demo)

| In scope for MVP hardening | Out of scope |
| --- | --- |
| Loopback bind by default | Multi-user authentication / SSO |
| Hostile PDF/DOCX parse sandbox | Network-exposed multi-tenant SaaS |
| Upload size / extension caps | Enterprise DLP or eDiscovery |
| Extractive citations (no invented prose) | Guaranteeing policy completeness |
| No automatic employment decisions | Regulatory certification (SOC2, ISO, etc.) |

## Document handling

- Uploads: max bytes (`upload_max_bytes`), allowed extensions, random storage names under `UPLOAD_DIR`.
- Parse in a **subprocess** with timeout, page cap, and extracted-text cap (`parsing/sandbox.py`).
- DOCX zip-bomb checks: uncompressed size and compression-ratio caps.
- Pathological PDF: unterminated inline image rejected (`parsing/hostile.py`).
- HTML seed/path strips script content (covered by tests).

## Answer integrity

- Answers are **extractive quotes** from indexed text. Optional LLM grounding is roadmap-only and unwired.
- Evidence thresholds force **abstention** when overlap/score gates fail (`domain/evidence.py`).
- Conflicting current policies are shown together; the system does not silently pick one.
- Citation rows store snippet + sha256 + version id so replacement cannot rewrite history unnoticed.

## Privacy and HR sensitivity

- Persistent UI banner when `APP_ENV=demo`: “Local demo · synthetic data.”
- Footer/preamble: not legal advice.
- No automated hire/reject/discipline actions are implemented.

## Operational failure modes

- Missing MiniLM or Qdrant → `/ready` degraded, sparse-only answers with UI notice.
- Stale ingest jobs reaped to `FAILED` on startup.
- Security response headers in FastAPI middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cache-Control: no-store`.

## Secrets and artifacts

- Do not commit `.env`, real policy PDFs with PII, model caches under `models/`, or upload dumps.
- [`.env.example`](.env.example) documents safe local defaults only.

## Claims verified against code (demo MVP)

| Claim | Code / test anchor |
| --- | --- |
| Loopback bind unless `ALLOW_NETWORK_BIND` | `config.enforce_loopback`; `test_refuses_non_loopback_without_flag` |
| Parse in subprocess with timeout + caps | `parsing/sandbox.py` → `app.parsing.worker` |
| DOCX zip-bomb / unterminated PDF image reject | `parsing/hostile.py`; `test_hostile_uploads_fail_quickly` |
| DB post-filter before cite | `retrieval.post_filter_chunks`; HR-1 tests |
| Citation snapshots survive replace | `test_citation_survives_replacement` |
| Abstain when evidence weak | `domain/evidence.py`; answering abstention path |
| Degraded `/ready` + sparse-only | `test_sparse_fallback_when_qdrant_is_down` |

## License

MIT — see [`LICENSE`](LICENSE).

## Related

- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Decisions: [`docs/ENGINEERING_DECISIONS.md`](docs/ENGINEERING_DECISIONS.md)
- Scope / limitations: [`README.md`](README.md#security-privacy-and-limitations)
