import type {
  Conversation,
  ConversationSummary,
  DocumentRecord,
  Overview,
  QueryResponse,
  ReadyInfo,
  SettingsInfo,
  VersionRecord,
  VersionText,
} from "./types.ts";

export class ApiError extends Error {
  code: string;

  constructor(message: string, code = "request_failed") {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (response.status === 204) {
    return undefined as T;
  }
  const payload = (await response.json().catch(() => null)) as
    | (T & { error?: string; code?: string })
    | null;
  if (!response.ok) {
    throw new ApiError(payload?.error || `Request failed (${response.status})`, payload?.code);
  }
  return payload as T;
}

export const api = {
  overview: () => request<Overview>("/api/overview"),
  settings: () => request<SettingsInfo>("/api/settings"),
  ready: () => request<ReadyInfo>("/ready"),
  documents: () => request<DocumentRecord[]>("/api/documents"),
  document: (id: string) => request<DocumentRecord>(`/api/documents/${id}`),
  versions: (id: string) => request<VersionRecord[]>(`/api/documents/${id}/versions`),
  versionText: (documentId: string, versionId: string) =>
    request<VersionText>(`/api/documents/${documentId}/versions/${versionId}`),
  conversations: () => request<ConversationSummary[]>("/api/conversations"),
  conversation: (id: string) => request<Conversation>(`/api/conversations/${id}`),
  query: (body: {
    question: string;
    conversation_id?: string;
    categories?: string[];
    audience?: string;
  }) =>
    request<QueryResponse>("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  upload: (form: FormData) => request<DocumentRecord>("/api/documents", { method: "POST", body: form }),
  replace: (id: string, form: FormData) =>
    request<DocumentRecord>(`/api/documents/${id}/versions`, { method: "POST", body: form }),
  remove: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  resetDemo: () => request<Overview>("/api/demo/reset", { method: "POST" }),
  deleteAll: () => request<Overview>("/api/demo/delete-all", { method: "POST" }),
};

export function sourceHref(citation: {
  document_id: string;
  document_version_id: string;
  chunk_id: string | null;
}) {
  const params = new URLSearchParams({ version: citation.document_version_id });
  if (citation.chunk_id) {
    params.set("chunk", citation.chunk_id);
  }
  return `/sources/${citation.document_id}?${params.toString()}`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

export function indexingLabel(state: string | null) {
  if (state === "indexed") return "Indexed";
  if (state === "indexed_sparse") return "Sparse only";
  if (state === "failed") return "Failed";
  if (state === "pending") return "Processing";
  return state || "Unknown";
}
