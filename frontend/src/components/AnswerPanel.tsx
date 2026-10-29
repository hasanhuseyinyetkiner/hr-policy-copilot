import { AlertTriangle, CircleOff, Quote, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { formatDate, sourceHref } from "../api.ts";
import type { Evidence, EvidenceThresholds, Message, RetrievalTelemetry } from "../types.ts";

export function AnswerPanel({ message }: { message: Message }) {
  const [telemetryOpen, setTelemetryOpen] = useState(false);
  if (message.role !== "assistant") {
    return null;
  }
  const abstained = message.mode === "abstain";
  const hasTelemetry = message.evidence.length > 0 || message.retrieval_telemetry != null;
  return (
    <article className="panel p-6 md:p-8" data-testid="answer" aria-live="polite">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <StatusPill message={message} />
        {message.retrieval_mode ? (
          <span className="rounded-full bg-[var(--paper)] px-3 py-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            {message.retrieval_mode} retrieval
          </span>
        ) : null}
        {hasTelemetry ? (
          <button
            type="button"
            className="rounded-full border border-[var(--line)] bg-[var(--paper)] px-3 py-1 text-xs font-medium text-[var(--accent-ink)]"
            onClick={() => setTelemetryOpen(true)}
            data-testid="open-telemetry"
          >
            Retrieval telemetry
          </button>
        ) : null}
      </div>
      {message.preamble ? <p className="text-sm text-[var(--muted)]">{message.preamble}</p> : null}
      {message.notice ? (
        <p className="mt-4 rounded-xl bg-[var(--warn-soft)] px-4 py-3 text-sm text-[var(--warn)]">
          {message.notice}
        </p>
      ) : null}
      {message.conflict_note ? (
        <p className="mt-4 rounded-xl bg-[var(--warn-soft)] px-4 py-3 text-sm text-[var(--warn)]">
          {message.conflict_note}
        </p>
      ) : null}
      {abstained ? (
        <div className="mt-8 flex items-start gap-3" data-testid="abstain">
          <CircleOff aria-hidden="true" />
          <p className="m-0 text-lg">No cited answer is available for this question.</p>
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-6">
          {message.citations.map((citation) => (
            <section key={citation.id} className="flex flex-col gap-3">
              <blockquote className="passage text-lg leading-relaxed">{citation.snippet}</blockquote>
              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <p className="m-0 text-[var(--muted)]">
                  {citation.document_title} · Rev {citation.revision} · effective{" "}
                  {formatDate(citation.effective_date)}
                  {citation.section_title ? ` · ${citation.section_title}` : ""}
                  {citation.page_number ? ` · p. ${citation.page_number}` : ""}
                </p>
                <Link
                  className="font-medium text-[var(--accent-ink)]"
                  to={sourceHref(citation)}
                  data-testid="citation-link"
                >
                  View source
                </Link>
              </div>
            </section>
          ))}
        </div>
      )}
      {message.superseded.map((hint) => (
        <p key={hint.document_version_id} className="mt-6 text-sm text-[var(--muted)]">
          {hint.note}{" "}
          <Link to={sourceHref({ ...hint, chunk_id: null })}>Read the superseded revision</Link>
        </p>
      ))}
      {telemetryOpen ? (
        <TelemetryDrawer
          evidence={message.evidence}
          thresholds={message.evidence_thresholds}
          telemetry={message.retrieval_telemetry}
          onClose={() => setTelemetryOpen(false)}
        />
      ) : null}
    </article>
  );
}

function TelemetryDrawer({
  evidence,
  thresholds,
  telemetry,
  onClose,
}: {
  evidence: Evidence[];
  thresholds: EvidenceThresholds | null;
  telemetry: RetrievalTelemetry | null;
  onClose: () => void;
}) {
  return (
    <div className="telemetry-overlay" role="dialog" aria-modal="true" aria-label="Retrieval telemetry">
      <button type="button" className="telemetry-backdrop" aria-label="Close telemetry" onClick={onClose} />
      <aside className="telemetry-drawer" data-testid="telemetry-drawer">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="m-0 text-xs font-medium uppercase tracking-[0.14em] text-[var(--accent-ink)]">
              Retrieval telemetry
            </p>
            <h2 className="m-0 mt-1 text-lg font-semibold">Scores, fusion, and gate</h2>
          </div>
          <button
            type="button"
            className="rounded-full border border-[var(--line)] p-2 text-[var(--muted)]"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>
        {telemetry ? (
          <dl
            className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm md:grid-cols-3"
            data-testid="retrieval-meta"
          >
            <div>
              <dt className="text-[var(--muted)]">Backend mode</dt>
              <dd className="m-0 font-medium">
                {telemetry.mode} · {telemetry.embedding_backend}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Corpus version</dt>
              <dd className="m-0 font-mono">{telemetry.corpus_version}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Latency</dt>
              <dd className="m-0 font-mono">{telemetry.latency_ms} ms</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Candidates</dt>
              <dd className="m-0 font-mono">
                bm25 {telemetry.bm25_candidates} · dense {telemetry.dense_candidates} · fused{" "}
                {telemetry.fused_candidates}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Filter rejected</dt>
              <dd className="m-0 font-mono">{telemetry.filter_rejected}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Threshold decision</dt>
              <dd className="m-0 font-medium">{telemetry.threshold_decision ?? "—"}</dd>
            </div>
          </dl>
        ) : null}
        {telemetry?.filter_rejections?.length ? (
          <p className="mb-4 text-sm text-[var(--muted)]" data-testid="filter-rejections">
            Post-filter drops:{" "}
            {telemetry.filter_rejections
              .slice(0, 6)
              .map((item) => `${item.reason}`)
              .join(", ")}
            {telemetry.filter_rejections.length > 6 ? "…" : ""}
          </p>
        ) : null}
        {thresholds ? (
          <p className="mb-4 text-sm text-[var(--muted)]" data-testid="abstention-thresholds">
            Gate: overlap ≥ {thresholds.min_overlap}, BM25 ≥ {thresholds.min_bm25}, or dense ≥{" "}
            {thresholds.min_cosine}. Max passages {thresholds.max_passages}.
          </p>
        ) : null}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[var(--muted)]">
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 font-medium">bm25</th>
                <th className="py-2 pr-3 font-medium">dense</th>
                <th className="py-2 pr-3 font-medium">RRF parts</th>
                <th className="py-2 pr-3 font-medium">rrf</th>
                <th className="py-2 pr-3 font-medium">Gate</th>
                <th className="py-2 font-medium">Used</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((row) => (
                <tr key={row.chunk_id} className="border-t border-[var(--line)] align-top">
                  <td className="py-2 pr-3">
                    {row.document_title} · Rev {row.revision}
                    <div className="text-[var(--muted)]">{row.preview}</div>
                    <div className="mt-1 text-xs text-[var(--muted)]">
                      overlap {row.overlap}
                      {row.clears_overlap ? " ✓" : " ✗"} · bm25
                      {row.clears_bm25 ? " ✓" : " ✗"} · dense
                      {row.clears_dense ? " ✓" : " ✗"}
                    </div>
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.bm25_score}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.dense_score ?? "—"}</td>
                  <td className="py-2 pr-3 font-mono text-xs">
                    b {row.bm25_rrf_contrib ?? 0} · d {row.dense_rrf_contrib ?? 0}
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs">{row.rrf_score}</td>
                  <td className="py-2 pr-3">
                    {row.clears_abstention_gate ? "pass" : "fail"}
                  </td>
                  <td className="py-2">{row.used ? "Yes" : row.rejected_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </aside>
    </div>
  );
}

function StatusPill({ message }: { message: Message }) {
  if (message.mode === "abstain") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-[var(--paper)] px-3 py-1 text-sm">
        <CircleOff size={14} aria-hidden="true" />
        {message.abstention_reason === "unsupported_version_scope"
          ? "Version scope unsupported"
          : "Insufficient evidence"}
      </span>
    );
  }
  if (message.contradictory) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-[var(--warn-soft)] px-3 py-1 text-sm text-[var(--warn)]">
        <AlertTriangle size={14} aria-hidden="true" /> Sources disagree
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-[var(--accent-soft)] px-3 py-1 text-sm text-[var(--accent-ink)]">
      <Quote size={14} aria-hidden="true" /> Evidence-backed
    </span>
  );
}
