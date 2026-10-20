# GitHub repository metadata

Suggested values for the GitHub “About” panel. Apply manually. Do not invent a live demo URL.

## Publication readiness (current)

| Dimension | Stance |
| --- | --- |
| Visibility | Prefer **private** until license is chosen and secrets scrubbed |
| License | **Pending** — no `LICENSE` file; do not market as open source |
| Demo | Local only — no public deployment URL |
| CI | Workflow present; badge valid only after the repo is on GitHub with Actions enabled |

## Description

(under ~150 characters for GitHub About)

```
Evidence-first HR policy assistant: hybrid BM25+dense+RRF, versioned sources, extractive citations, honest abstention.
```

## Topics

Do **not** add `open-source` until a `LICENSE` file exists and redistribution terms are chosen.

```
rag
hybrid-retrieval
bm25
fastapi
qdrant
sentence-transformers
hr-tech
typescript
react
trustworthy-ai
```

## Homepage

Leave empty unless a public demo is published.

## Pin / portfolio rationale

Pin this repo when showcasing **trustworthy retrieval** for HR: hybrid search, document versioning, extractive citations, and abstention under weak evidence — with labeled synthetic evaluation (hash fixture + measured MiniLM on n=11; not inflated held-out claims).

Suggested pin blurb (short):

```
Hybrid BM25+dense HR policy Q&A with versioned citations and honest abstention — local demo, synthetic corpus.
```

## Notes

- CI badge (after GitHub remote exists): `https://github.com/hasanhuseyinyetkiner/hr-policy-copilot/actions/workflows/ci.yml/badge.svg`
- Primary docs: root [`README.md`](../README.md); deep dives under [`docs/`](./)
- Release checklist: [`RELEASE_READINESS.md`](RELEASE_READINESS.md)
