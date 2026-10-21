# Engineering decisions — HR Policy Copilot

Long-form Context → Options → Decision → Trade-offs → Validation for the choices that define this system. Architecture overview: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Hybrid BM25 + dense + Reciprocal Rank Fusion

### Context

HR policy questions mix exact phrases (“25 days of annual leave”) with paraphrases (“how much PTO”). Lexical-only search misses paraphrase; dense-only search can drift toward thematically similar but wrong clauses.

### Options

1. **Sparse only** (BM25 / FTS) — strong on exact terms, weak on paraphrase.
2. **Dense only** (MiniLM + Qdrant) — better semantic recall, weaker on rare identifiers and brittle under offline/degraded conditions.
3. **Hybrid with late fusion (RRF)** — run both, fuse ranks without calibrating score scales.

### Decision

Default path is **hybrid**: DB-backed BM25 candidates + Qdrant dense candidates → `reciprocal_rank_fusion` (`rrf_k=60`) → DB post-filter → evidence gate (`services/retrieval.py`, `domain/fusion.py`). Eval and API accept `retrieval_preference` of `hybrid` | `dense` | `sparse` for ablation.

### Trade-offs

- RRF avoids cross-normalizing BM25 vs cosine but can promote mediocre dual-list items.
- Two indexes to keep consistent (mitigated by post-filter + reconcile).
- Dense path adds model/Qdrant operational surface; sparse fallback preserves demo usefulness.

### Validation

- Unit: `test_rrf_rewards_agreement`, BM25 preference tests in `tests/test_domain.py`.
- Integration: conflict / leave / abstain flows in `tests/test_api.py`.
- Fixture eval (hash embedder): `docs/EVALUATION.md` / `docs/EVAL_RESULTS.json`. MiniLM: `docs/EVAL_RESULTS_MINILM.json`. Neither is a held-out production benchmark.

---

## 2. Database as source of truth for every citeable hit

### Context

Vector stores and in-memory rankers can return stale IDs after replace/delete. Citing a superseded remote-work clause as current would be an HR trust failure.

### Options

1. Trust Qdrant payloads as authoritative.
2. Dual-write carefully and hope.
3. **Always re-validate hits against current relational rows** before display or citation.

### Decision

**PostgreSQL/SQLite is authoritative** (HR-1). `post_filter_chunks` requires `Chunk.is_current`, `DocumentVersion.is_current`, non-deleted document, and audience (plus optional category). Fault-injection test commits the DB supersede then fails before vector delete; superseded chunks must not appear.

### Trade-offs

- Extra DB round-trip on query (acceptable for demo-scale corpora).
- Qdrant can briefly hold orphans until reconcile — reconcile script exists for ops.

### Validation

- `test_fault_injection_hides_superseded_vectors`
- `test_conflict_quotes_both_current_sources_and_hides_superseded`
- `test_reconcile_removes_stale_points_and_restores_missing`

---

## 3. Versioned corpus + citation snapshots (not live re-fetch)

### Context

Policies revise. Conversations must remain auditable: “what did we show when we answered?” must not silently morph when a PDF is replaced.

### Options

1. Store only chunk IDs; re-resolve text at read time.
2. Hard-delete old text when replaced.
3. Soft-supersede versions; **snapshot snippet + sha256 + `document_version_id` on each citation**.

### Decision

Option 3 (HR-4). Ingest soft-deletes prior versions/chunks, removes their vectors, keeps citation rows intact. UI can open the superseded revision from hints when relevant.

### Trade-offs

- Storage grows with revision history (fine for demo).
- Operators must understand “current answer” vs “historical citation.”

### Validation

- `test_citation_survives_replacement`
- Seeded obsolete Remote Work Rev 1 vs current Rev 2 in conflict demo

---

## 4. Extractive answers + evidence thresholds + abstention

### Context

Unconstrained LLM “policy answers” are easy to demo and dangerous for HR: fluent, uncited, and wrong. This MVP deliberately stays extractive.

### Options

1. Free-form generation with optional citations.
2. Retrieval-augmented generation with faithfulness checks later.
3. **Quote stored passages only**; require token overlap and BM25-or-cosine thresholds; abstain otherwise; surface contradictions instead of picking a winner.

### Decision

Option 3. `passes_threshold` / `choose_passages` in `domain/evidence.py`; answering layer writes extractive preamble or abstention preamble (`services/answering.py`). Instruction-override chunks are never selected. Conflicting in-office-day claims → quote both + “Sources disagree.”

### Trade-offs

- Answers can feel terse vs chatbot prose (by design).
- Thresholds are heuristic and corpus-tuned — not a calibrated confidence model.
- Optional Ollama/cloud grounding remains **roadmap**, not shipped.

### Validation

- `test_extractive_citation_is_exact_and_unanswerable_abstains`
- `test_instruction_override_is_not_selected`
- Playwright screenshots: `docs/screenshots/answer-*.png`, `abstain-*.png`
- Eval abstention rows in `data/eval/questions.jsonl`

---

## 5. Hostile upload sandbox and parser caps

### Context

Policy libraries accept PDF/DOCX/HTML/TXT. Parsers are a classic attack surface (zip bombs, pathological PDFs, event-loop stalls).

### Options

1. Parse in-process with library defaults.
2. **Subprocess parse with timeout + size/page/text caps + DOCX zip inspection + unterminated inline-image reject**; pin patched `pypdf`.

### Decision

Option 2 (HR-3, `parsing/sandbox.py`, `parsing/hostile.py`). Heavy work off the asyncio event loop (`run_in_threadpool`); `/health` must stay responsive during ingest.

### Trade-offs

- Stricter rejects mean some valid weird PDFs fail closed.
- Subprocess overhead on every upload (acceptable at demo volume).

### Validation

- `test_hostile_uploads_fail_quickly`
- `test_unterminated_inline_image_detector`, `test_docx_zip_bomb_and_size_cap`
- `test_health_stays_responsive_during_ingest`

---

## 6. Honest degraded / offline dense path

### Context

MiniLM and Qdrant are optional operationally: laptops without the model cache, CI with hash embedder, or Qdrant path locks.

### Options

1. Hard-fail all queries without dense.
2. Silent sparse fallback.
3. **`/ready` degraded + sparse-only retrieval + visible UI notice** (HR-5).

### Decision

Option 3. Local Qdrant path mode for single-process native dev; Compose uses the server. `HF_HUB_OFFLINE=1` by default after `make models` / `python -m app.download_model`.

### Trade-offs

- Degraded answers may miss paraphrases — disclosed in UI.
- Hash embedder in tests/eval is **fixture-only**; quote MiniLM only from `docs/EVALUATION.md` / `--backend local` runs.

### Validation

- `test_sparse_fallback_when_qdrant_is_down`
- `test_health_is_ok_and_ready_reports_hash_backend`
- Eval runner forces `embedding_backend="hash"` in `scripts/run_eval.py`
