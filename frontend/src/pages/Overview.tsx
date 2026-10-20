import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { api, formatDate, indexingLabel } from "../api.ts";
import { ErrorBlock, LoadingBlock } from "../components/States.tsx";

export function OverviewPage() {
  const navigate = useNavigate();
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });

  if (overview.isLoading) {
    return (
      <div className="page">
        <LoadingBlock label="Loading the library counts" />
      </div>
    );
  }
  if (overview.isError || !overview.data) {
    return (
      <div className="page">
        <ErrorBlock message={overview.error?.message ?? "Overview unavailable"} onRetry={() => overview.refetch()} />
      </div>
    );
  }
  const data = overview.data;
  const stats = [
    { label: "Indexed documents", value: data.documents },
    { label: "Categories in use", value: data.categories_in_use },
    { label: "Current passages", value: data.chunks },
    { label: "Versions stored", value: data.versions },
  ];

  return (
    <div className="page flex flex-col gap-8">
      <header className="max-w-3xl">
        <p className="m-0 text-sm font-medium uppercase tracking-[0.14em] text-[var(--accent-ink)]">
          Evidence first
        </p>
        <h1 className="mb-3 mt-2 text-4xl font-semibold tracking-tight md:text-5xl">
          What does the policy actually say?
        </h1>
        <p className="text-lg text-[var(--muted)]">
          Ask in plain language. The answer is a quote from a versioned source, or an explicit refusal
          when the library does not support one.
        </p>
      </header>
      <section className="grid gap-4 md:grid-cols-4" aria-label="Library counts">
        {stats.map((stat) => (
          <article key={stat.label} className="panel p-5">
            <p className="m-0 text-sm text-[var(--muted)]">{stat.label}</p>
            <p className="stat-value m-0 mt-2">{stat.value}</p>
          </article>
        ))}
      </section>
      <section className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <div>
          <h2 className="text-xl">Try a question</h2>
          <div className="flex flex-col gap-3">
            {data.examples.map((example) => (
              <button
                key={example.id}
                type="button"
                className="panel flex items-start justify-between gap-4 p-4 text-left"
                onClick={() => navigate(`/ask?q=${encodeURIComponent(example.question)}`)}
              >
                <span>
                  <span className="block font-medium">{example.question}</span>
                  <span className="mt-1 block text-sm text-[var(--muted)]">{example.blurb}</span>
                </span>
                <ArrowRight aria-hidden="true" />
              </button>
            ))}
          </div>
        </div>
        <div>
          <h2 className="text-xl">Recently updated</h2>
          {data.recent_documents.length === 0 ? (
            <p className="text-[var(--muted)]">No documents are indexed yet.</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {data.recent_documents.map((document) => (
                <li key={document.id} className="panel p-4">
                  <Link className="font-medium text-[var(--ink)]" to={`/documents/${document.id}`}>
                    {document.title}
                  </Link>
                  <p className="m-0 mt-1 text-sm text-[var(--muted)]">
                    Rev {document.current_revision ?? "—"} · {document.category_label} ·{" "}
                    {indexingLabel(document.indexing_state)} · {formatDate(document.effective_date)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
