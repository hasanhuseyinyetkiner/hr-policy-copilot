import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api.ts";
import { ErrorBlock, LoadingBlock } from "../components/States.tsx";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const ready = useQuery({ queryKey: ["ready"], queryFn: api.ready });
  const reset = useMutation({
    mutationFn: api.resetDemo,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });
  const wipe = useMutation({
    mutationFn: api.deleteAll,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });

  if (settings.isLoading || ready.isLoading) {
    return (
      <div className="page">
        <LoadingBlock label="Loading status" />
      </div>
    );
  }
  if (settings.isError || !settings.data) {
    return (
      <div className="page">
        <ErrorBlock message={settings.error?.message ?? "Settings unavailable"} onRetry={() => settings.refetch()} />
      </div>
    );
  }
  const info = settings.data;
  const rows = [
    ["Environment", info.app_env],
    ["Answer mode", info.llm_mode],
    ["External model calls", info.external_llm_calls ? "Yes" : "No"],
    ["Embedding model", info.embedding_model],
    ["Embedding dimensions", String(info.embedding_dimensions)],
    ["Embedding license", info.embedding_license],
    ["Embedding files", info.embedding_ready ? "Present" : "Missing"],
    ["Retrieval", info.retrieval],
    ["Loopback only", info.loopback_only ? "Yes" : "No"],
    ["Readiness", ready.data?.status ?? "unknown"],
    ["Database", ready.data?.checks.database.ok ? "Reachable" : "Unavailable"],
    ["Qdrant", ready.data?.checks.qdrant.detail ?? "Unknown"],
  ];

  return (
    <div className="page flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="m-0 text-3xl font-semibold tracking-tight">Status and limits</h1>
        <p className="text-[var(--muted)]">
          The demo does not call a hosted language model. Counts and readiness come from this API.
        </p>
      </header>
      <dl className="panel m-0 grid gap-4 p-6">
        {rows.map(([label, value]) => (
          <div key={label} className="grid gap-1 border-b border-[var(--line)] pb-3 md:grid-cols-[12rem_1fr]">
            <dt className="text-sm text-[var(--muted)]">{label}</dt>
            <dd className="m-0">{value}</dd>
          </div>
        ))}
      </dl>
      <section>
        <h2 className="text-xl">Limitations</h2>
        <ul>
          {info.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section className="panel flex flex-col gap-3 p-5">
        <h2 className="m-0 text-lg">Demo data</h2>
        <p className="m-0 text-sm text-[var(--muted)]">
          Reset replaces the library with the synthetic corpus. Delete all removes documents, conversations,
          and vectors from this local demo.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
            onClick={() => reset.mutate()}
            disabled={reset.isPending}
          >
            Reseed synthetic policies
          </button>
          <button
            type="button"
            className="rounded-full border border-[var(--warn)] px-4 py-2 text-sm text-[var(--warn)] disabled:opacity-60"
            disabled={wipe.isPending}
            onClick={() => {
              if (window.confirm("Delete all local demo documents and conversations?")) {
                wipe.mutate();
              }
            }}
          >
            Delete all demo data
          </button>
        </div>
        {reset.isError ? <p className="m-0 text-sm text-[var(--warn)]">{reset.error.message}</p> : null}
        {wipe.isError ? <p className="m-0 text-sm text-[var(--warn)]">{wipe.error.message}</p> : null}
      </section>
    </div>
  );
}
