import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, formatDate, indexingLabel } from "../api.ts";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/States.tsx";

export function LibraryPage() {
  const queryClient = useQueryClient();
  const documents = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("company_policy");
  const [effectiveDate, setEffectiveDate] = useState("2026-01-01");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file first.");
      const form = new FormData();
      form.set("file", file);
      form.set("title", title);
      form.set("category", category);
      form.set("effective_date", effectiveDate);
      form.set("source_label", "Synthetic — user upload");
      form.set("audience", "staff");
      return api.upload(form);
    },
    onSuccess: async (document) => {
      setMessage(
        document.indexing_state === "failed"
          ? document.extraction_error || "Indexing failed."
          : `${document.title} is ${indexingLabel(document.indexing_state).toLowerCase()}.`,
      );
      setTitle("");
      setFile(null);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      await queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.remove(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      await queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  return (
    <div className="page flex flex-col gap-6">
      <header>
        <h1 className="m-0 text-3xl font-semibold tracking-tight">Document library</h1>
        <p className="text-[var(--muted)]">
          PDF, DOCX, TXT, and HTML. Replacing a file keeps the old revision for past citations.
        </p>
      </header>
      <form
        className="panel grid gap-3 p-4 md:grid-cols-4"
        onSubmit={(event) => {
          event.preventDefault();
          upload.mutate();
        }}
      >
        <label className="text-sm">
          Title
          <input
            className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--paper)] px-3 py-2"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          Category
          <select
            className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--paper)] px-3 py-2"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="company_policy">Company policy</option>
            <option value="regulatory_briefing">Regulatory briefing</option>
          </select>
        </label>
        <label className="text-sm">
          Effective date
          <input
            className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--paper)] px-3 py-2"
            type="date"
            value={effectiveDate}
            onChange={(event) => setEffectiveDate(event.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          File
          <input
            className="mt-1 w-full text-sm"
            type="file"
            accept=".pdf,.docx,.txt,.html,.htm"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
        </label>
        <div className="md:col-span-4 flex items-center justify-between gap-3">
          <p className="m-0 text-sm text-[var(--muted)]">{message}</p>
          <button
            type="submit"
            className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
            disabled={upload.isPending}
          >
            Upload
          </button>
        </div>
        {upload.isError ? <p className="m-0 text-sm text-[var(--warn)]">{upload.error.message}</p> : null}
      </form>
      {documents.isLoading ? <LoadingBlock label="Loading documents" /> : null}
      {documents.isError ? (
        <ErrorBlock message={documents.error.message} onRetry={() => documents.refetch()} />
      ) : null}
      {documents.data && documents.data.length === 0 ? (
        <EmptyBlock title="Nothing indexed" body="Upload a synthetic policy or reseed the demo from Settings." />
      ) : null}
      {documents.data && documents.data.length > 0 ? (
        <div className="panel overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="text-[var(--muted)]">
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Revision</th>
                <th className="px-4 py-3 font-medium">Effective</th>
                <th className="px-4 py-3 font-medium">Pages</th>
                <th className="px-4 py-3 font-medium">State</th>
                <th className="px-4 py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {documents.data.map((document) => (
                <tr key={document.id} className="border-t border-[var(--line)]" data-testid="library-row">
                  <td className="px-4 py-3">
                    <Link className="font-medium text-[var(--ink)]" to={`/documents/${document.id}`}>
                      {document.title}
                    </Link>
                    <div className="text-[var(--muted)]">{document.original_filename}</div>
                    {document.extraction_error ? (
                      <div className="text-[var(--warn)]">{document.extraction_error}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">{document.category_label}</td>
                  <td className="px-4 py-3">{document.current_revision ?? "—"}</td>
                  <td className="px-4 py-3">{formatDate(document.effective_date)}</td>
                  <td className="px-4 py-3">{document.page_count ?? "—"}</td>
                  <td className="px-4 py-3">{indexingLabel(document.indexing_state)}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      className="text-sm text-[var(--warn)]"
                      onClick={() => {
                        if (window.confirm(`Delete ${document.title}? Past citations keep their quoted text.`)) {
                          remove.mutate(document.id);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
