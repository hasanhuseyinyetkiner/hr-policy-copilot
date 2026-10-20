export function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="panel p-6" role="status">
      <p className="m-0 text-sm text-[var(--muted)]">{label}</p>
      <div className="mt-4 h-3 w-2/3 animate-pulse rounded bg-[var(--line)]" />
      <div className="mt-3 h-3 w-1/2 animate-pulse rounded bg-[var(--line)]" />
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="panel border-[var(--warn)] p-6" role="alert">
      <p className="m-0 font-medium">Something went wrong</p>
      <p className="text-sm text-[var(--muted)]">{message}</p>
      {onRetry ? (
        <button
          type="button"
          className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
          onClick={onRetry}
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="panel p-8">
      <h2 className="m-0 text-xl">{title}</h2>
      <p className="text-[var(--muted)]">{body}</p>
    </div>
  );
}
