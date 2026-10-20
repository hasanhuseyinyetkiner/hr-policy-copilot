import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { api, formatDate, indexingLabel } from "../api.ts";
import { ErrorBlock, LoadingBlock } from "../components/States.tsx";

export function VersionsPage() {
  const { documentId = "" } = useParams();
  const queryClient = useQueryClient();
  const document = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.document(documentId),
  });
  const versions = useQuery({
    queryKey: ["versions", documentId],
    queryFn: () => api.versions(documentId),
  });
  const [effectiveDate, setEffectiveDate] = useState("2026-06-01");
  const [file, setFile] = useState<File | null>(null);

  const replace = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose the replacement file.");
      const form = new FormData();
      form.set("file", file);
      form.set("effective_date", effectiveDate);
      return api.replace(documentId, form);
    },
    onSuccess: async () => {
      setFile(null);
      await queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      await queryClient.invalidateQueries({ queryKey: ["versions", documentId] });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  if (document.isLoading || versions.isLoading) {
    return (
      <div className="page">
        <LoadingBlock label="Loading revisions" />
      </div>
    );
  }
  if (document.isError || !document.data) {
    return (
      <div className="page">
        <ErrorBlock message={document.error?.message ?? "Document unavailable"} onRetry={() => document.refetch()} />
      </div>
    );
  }
  const record = document.data;
  return (
    <div className="page flex flex-col gap-6">
      <header>
        <p className="m-0 text-sm text-[var(--muted)]">{record.category_label}</p>
        <h1 className="mb-2 mt-1 text-3xl font-semibold tracking-tight">{record.title}</h1>
        <p className="text-[var(--muted)]">
          {record.source_label} · {record.chunk_count} current passages · {indexingLabel(record.indexing_state)}
        </p>
      </header>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {(versions.data ?? []).map((version) => (
          <li key={version.id} className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <strong>Revision {version.revision}</strong>
              <p className="m-0 text-sm text-[var(--muted)]">
                Effective {formatDate(version.effective_date)} · {version.original_filename} ·{" "}
                {version.is_current ? "Current" : "Superseded"} · {indexingLabel(version.indexing_state)}
              </p>
              {version.extraction_error ? (
                <p className="m-0 text-sm text-[var(--warn)]">{version.extraction_error}</p>
              ) : null}
            </div>
            <Link to={`/sources/${record.id}?version=${version.id}`}>Read text</Link>
          </li>
        ))}
      </ol>
      <form
        className="panel flex flex-col gap-3 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          replace.mutate();
        }}
      >
        <h2 className="m-0 text-lg">Upload a new revision</h2>
        <label className="text-sm">
          Effective date
          <input
            className="mt-1 block rounded-xl border border-[var(--line)] bg-[var(--paper)] px-3 py-2"
            type="date"
            value={effectiveDate}
            onChange={(event) => setEffectiveDate(event.target.value)}
            required
          />
        </label>
        <input
          type="file"
          accept=".pdf,.docx,.txt,.html,.htm"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          required
        />
        <button
          type="submit"
          className="w-fit rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
          disabled={replace.isPending}
        >
          Replace current revision
        </button>
        {replace.isError ? <p className="m-0 text-sm text-[var(--warn)]">{replace.error.message}</p> : null}
      </form>
    </div>
  );
}
