import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { api } from "../api.ts";
import { AnswerPanel } from "../components/AnswerPanel.tsx";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/States.tsx";
import type { Message } from "../types.ts";

export function AskPage() {
  const { conversationId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: api.conversations });
  const thread = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => api.conversation(conversationId!),
    enabled: Boolean(conversationId),
  });
  const [question, setQuestion] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const launched = useRef("");

  const ask = useMutation({
    mutationFn: (text: string) =>
      api.query({
        question: text,
        conversation_id: conversationId,
        categories: categories.length ? categories : undefined,
      }),
    onSuccess: async (result) => {
      setQuestion("");
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["conversation", result.conversation_id] });
      if (result.conversation_id !== conversationId) {
        navigate(`/ask/${result.conversation_id}`, { replace: true });
      }
    },
  });

  useEffect(() => {
    const preset = searchParams.get("q");
    if (!preset || launched.current === preset) return;
    launched.current = preset;
    ask.mutate(preset);
  }, [searchParams, ask]);

  function toggleCategory(key: string) {
    setCategories((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || ask.isPending) return;
    ask.mutate(text);
  }

  const messages: Message[] = thread.data?.messages ?? [];
  const pendingAnswer = ask.data && ask.data.conversation_id === conversationId ? null : ask.data;

  return (
    <div className="page grid gap-6 lg:grid-cols-[16rem_1fr]">
      <aside>
        <h2 className="text-sm font-medium uppercase tracking-wide text-[var(--muted)]">Conversations</h2>
        {conversations.data && conversations.data.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">No questions yet.</p>
        ) : null}
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {(conversations.data ?? []).map((item) => (
            <li key={item.id}>
              <Link
                className="block rounded-xl px-3 py-2 text-sm text-[var(--ink)]"
                to={`/ask/${item.id}`}
              >
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      </aside>
      <section className="flex flex-col gap-5">
        <header>
          <h1 className="m-0 text-3xl font-semibold tracking-tight">Ask the library</h1>
          <p className="text-[var(--muted)]">
            Filters apply before search. An answer is either a direct quote or an abstention.
          </p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Category filters">
            {(overview.data?.categories ?? []).map((category) => {
              const selected = categories.includes(category.key);
              return (
                <button
                  key={category.key}
                  type="button"
                  aria-pressed={selected}
                  className={
                    selected
                      ? "rounded-full bg-[var(--accent)] px-3 py-1 text-sm text-white"
                      : "rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-1 text-sm"
                  }
                  onClick={() => toggleCategory(category.key)}
                >
                  {category.label}
                </button>
              );
            })}
          </div>
        </header>
        {thread.isLoading ? <LoadingBlock label="Loading the conversation" /> : null}
        {thread.isError ? (
          <ErrorBlock message={thread.error.message} onRetry={() => thread.refetch()} />
        ) : null}
        {messages.length === 0 && !ask.isPending && !pendingAnswer ? (
          <EmptyBlock
            title="Start with a seeded policy"
            body="The examples on the overview are written so a real passage can answer them, or so the library correctly abstains."
          />
        ) : null}
        {messages.map((message, index) =>
          message.role === "user" ? (
            <h2 key={message.id} className="m-0 text-2xl font-semibold tracking-tight">
              {message.content}
              <span className="sr-only"> question {index + 1}</span>
            </h2>
          ) : (
            <AnswerPanel key={message.id} message={message} />
          ),
        )}
        {ask.isPending ? <LoadingBlock label="Searching indexed passages" /> : null}
        {ask.isError ? <ErrorBlock message={ask.error.message} /> : null}
        {pendingAnswer && pendingAnswer.conversation_id !== conversationId ? (
          <AnswerPanel message={pendingAnswer} />
        ) : null}
        <form className="panel flex flex-col gap-3 p-4" onSubmit={onSubmit}>
          <label className="text-sm font-medium" htmlFor="question">
            Policy question
          </label>
          <textarea
            id="question"
            className="min-h-24 resize-y rounded-xl border border-[var(--line)] bg-[var(--paper)] p-3"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="Ask about leave, office days, expenses, or onboarding"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              className="rounded-full bg-[var(--accent)] px-5 py-2 font-medium text-white disabled:opacity-60"
              disabled={ask.isPending || question.trim().length === 0}
            >
              Ask
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
