# Release readiness — Senior Engineering Portfolio

Checklist for making this repository presentable as a portfolio artifact. Status reflects the local workspace as of documentation polish on **2026-10-20**. This is not a production SaaS go-live plan.

## Ready (evidence-backed)

| Item | Evidence |
| --- | --- |
| Native demo path documented | Root README Quick start; ports `8101` / `5101` |
| Architecture + decisions docs | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`ENGINEERING_DECISIONS.md`](ENGINEERING_DECISIONS.md) |
| Binding constraints recorded | [`REVIEW_AMENDMENTS.md`](REVIEW_AMENDMENTS.md) |
| Security / privacy boundaries | [`SECURITY.md`](SECURITY.md); audience ≠ auth; loopback default |
| Authentic screenshots | [`screenshots/`](screenshots/) light/dark pairs from `pnpm screenshots` |
| CI workflow present | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (backend + frontend + compose-smoke) |
| Hash fixture eval | n=11, hybrid/dense/sparse — [`EVAL.md`](EVAL.md) |
| MiniLM eval (same seed) | Measured 2026-10-20 — [`EVAL_MINILM.md`](EVAL_MINILM.md) |
| Frontend docs | [`../frontend/README.md`](../frontend/README.md) replaces Vite template |
| Historical prompt labeled | [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) marked historical |

## Blockers before “public portfolio release”

Default recommendation: keep the repository **private** with **license pending** until the owner explicitly chooses otherwise.

| Blocker | Why it matters | Owner action |
| --- | --- | --- |
| **No `LICENSE` file** | Without a license, others have no clear redistribution rights; do not market as open source | Choose and add a license (or keep private and state “all rights reserved”) |
| **Visibility / remotes** | Pushing public without license + scrub is risky | Keep private until ready; scrub secrets before any public push |
| **No multi-user auth** | Anyone who can reach the bind address can mutate the library | Keep loopback / VPN; do not advertise as multi-tenant SaaS |
| **Synthetic-only corpus** | Real HR PDFs may contain PII | Do not upload real employee data; keep demo seed |
| **Eval scale** | n=11 synthetic; scores saturated at 1.00 | Do not claim production accuracy; optional larger labeled set later |
| **Optional LLM grounding unwired** | Spec briefly mentioned Ollama/cloud | Keep labeled roadmap; do not imply shipped generative answers |
| **Compose verified in CI only** | Authoring machine may lack Docker | README already discloses; ensure CI green on the publish commit |

## Do not invent for release

- Live demo URLs, coverage percentages, latency SLOs, or “production ready / compliant / bias-free” claims
- MiniLM scores without a local `--backend local` run (runner exits if model missing)
- Screenshots that are not from `pnpm screenshots` / a real local session

## Suggested publish sequence (owner-driven)

1. Choose license (or keep private).
2. Confirm CI green on the intended commit.
3. Apply [`GITHUB_METADATA.md`](GITHUB_METADATA.md) About text and topics (omit `open-source` until licensed).
4. Push / set visibility only with explicit owner authorization.
5. Pin for portfolio with the trustworthy-retrieval narrative (abstention + citations + versioning).

## Related

- Evaluation narrative: [`EVALUATION.md`](EVALUATION.md)
- Security: [`SECURITY.md`](SECURITY.md)
- GitHub About: [`GITHUB_METADATA.md`](GITHUB_METADATA.md)
