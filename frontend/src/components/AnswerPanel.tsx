import { AlertTriangle, CircleOff, Quote } from "lucide-react";
import { Link } from "react-router";
import { formatDate, sourceHref } from "../api.ts";
import type { Message } from "../types.ts";

export function AnswerPanel({ message }: { message: Message }) {
  if (message.role !== "assistant") {
    return null;
  }
  const abstained = message.mode === "abstain";
  return (
    <article className="panel p-6 md:p-8" data-testid="answer" aria-live="polite">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <StatusPill message={message} />
        {message.retrieval_mode ? (
          <span className="rounded-full bg-[var(--paper)] px-3 py-1 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            {message.retrieval_mode} retrieval
          </span>
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
      {message.evidence.length > 0 ? (
        <details className="mt-8">
          <summary className="cursor-pointer text-sm font-medium">Retrieval inspector</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="text-[var(--muted)]">
                  <th className="py-2 pr-3 font-medium">Source</th>
                  <th className="py-2 pr-3 font-medium">BM25</th>
                  <th className="py-2 pr-3 font-medium">Dense</th>
                  <th className="py-2 pr-3 font-medium">RRF</th>
                  <th className="py-2 font-medium">Used</th>
                </tr>
              </thead>
              <tbody>
                {message.evidence.map((row) => (
                  <tr key={row.chunk_id} className="border-t border-[var(--line)]">
                    <td className="py-2 pr-3">
                      {row.document_title} · Rev {row.revision}
                      <div className="text-[var(--muted)]">{row.preview}</div>
                    </td>
                    <td className="py-2 pr-3">{row.bm25_score}</td>
                    <td className="py-2 pr-3">{row.dense_score ?? "—"}</td>
                    <td className="py-2 pr-3">{row.rrf_score}</td>
                    <td className="py-2">{row.used ? "Yes" : row.rejected_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </article>
  );
}

function StatusPill({ message }: { message: Message }) {
  if (message.mode === "abstain") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-[var(--paper)] px-3 py-1 text-sm">
        <CircleOff size={14} aria-hidden="true" /> Insufficient evidence
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
