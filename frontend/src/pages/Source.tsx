import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { api, formatDate } from "../api.ts";
import { ErrorBlock, LoadingBlock } from "../components/States.tsx";

export function SourcePage() {
  const { documentId = "" } = useParams();
  const [params] = useSearchParams();
  const versionId = params.get("version") ?? "";
  const chunkId = params.get("chunk");
  const document = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.document(documentId),
    enabled: Boolean(documentId),
  });
  const versions = useQuery({
    queryKey: ["versions", documentId],
    queryFn: () => api.versions(documentId),
    enabled: Boolean(documentId),
  });
  const selected = versionId || document.data?.version_id || "";
  const text = useQuery({
    queryKey: ["version-text", documentId, selected],
    queryFn: () => api.versionText(documentId, selected),
    enabled: Boolean(documentId && selected),
  });

  useEffect(() => {
    if (!chunkId) return;
    window.document.getElementById(`chunk-${chunkId}`)?.scrollIntoView({ block: "center" });
  }, [chunkId, text.data]);

  if (text.isLoading || document.isLoading) {
    return (
      <div className="page">
        <LoadingBlock label="Opening the source" />
      </div>
    );
  }
  if (text.isError || !text.data) {
    return (
      <div className="page">
        <ErrorBlock message={text.error?.message ?? "Source unavailable"} onRetry={() => text.refetch()} />
      </div>
    );
  }
  const payload = text.data;
  const citedChunk = payload.chunks.find((chunk) => chunk.id === chunkId) ?? null;
  return (
    <div className="page source-split">
      <aside className="source-nav flex flex-col gap-3 text-sm">
        <Link to={`/documents/${documentId}`}>All revisions</Link>
        {payload.document.policy_id ? (
          <p className="m-0 font-mono text-xs text-[var(--accent-ink)]">{payload.document.policy_id}</p>
        ) : null}
        <p className="m-0 text-[var(--muted)]">{payload.document.source_label}</p>
        <p className="m-0">{payload.document.category_label}</p>
        <nav className="mt-2 flex flex-col gap-1" aria-label="Revisions">
          {(versions.data ?? []).map((version) => (
            <Link
              key={version.id}
              to={`/sources/${documentId}?version=${version.id}${chunkId ? `&chunk=${chunkId}` : ""}`}
              aria-current={version.id === payload.version.id ? "page" : undefined}
              className="rounded-lg px-2 py-1.5"
            >
              Revision {version.revision}
              {version.is_current ? " · current" : " · superseded"}
            </Link>
          ))}
        </nav>
        {citedChunk ? (
          <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--paper)] p-3">
            <p className="m-0 text-xs font-medium uppercase tracking-wide text-[var(--accent-ink)]">
              Cited passage
            </p>
            <p className="mt-2 mb-0 text-sm leading-relaxed">{citedChunk.text.slice(0, 220)}
              {citedChunk.text.length > 220 ? "…" : ""}
            </p>
          </div>
        ) : null}
      </aside>
      <article className="panel source-reader p-6 md:p-10">
        <p className="m-0 text-sm font-medium uppercase tracking-[0.14em] text-[var(--accent-ink)]">
          Source viewer
        </p>
        <h1 className="mb-2 mt-2 text-3xl font-semibold tracking-tight">{payload.document.title}</h1>
        <p className="text-sm text-[var(--muted)]">
          Revision {payload.version.revision} · effective {formatDate(payload.version.effective_date)} ·{" "}
          {payload.version.original_filename}
          {payload.document.deleted ? " · deleted from the library" : ""}
        </p>
        {!payload.version.is_current ? (
          <p className="rounded-xl bg-[var(--warn-soft)] px-4 py-3 text-sm text-[var(--warn)]">
            This revision was superseded
            {payload.version.superseded_at ? ` on ${formatDate(payload.version.superseded_at)}` : ""}. It
            stays available so older answers can still be checked.
          </p>
        ) : null}
        <div className="mt-8 flex flex-col gap-6">
          {payload.chunks.map((chunk) => {
            const cited = chunk.id === chunkId;
            return (
              <section
                key={chunk.id}
                id={`chunk-${chunk.id}`}
                className={cited ? "cited-chunk is-cited" : "cited-chunk"}
                data-testid={cited ? "cited-passage" : undefined}
              >
                <p className="m-0 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                  {chunk.section_title || "Passage"}
                  {chunk.page_number ? ` · page ${chunk.page_number}` : ""}
                  {cited ? " · cited passage" : ""}
                </p>
                <p className="whitespace-pre-wrap text-base leading-relaxed">{chunk.text}</p>
              </section>
            );
          })}
        </div>
      </article>
    </div>
  );
}
