export type Category = {
  key: string;
  label: string;
  description: string;
  document_count: number;
};

export type DocumentRecord = {
  id: string;
  title: string;
  policy_id: string | null;
  category: string;
  category_label: string;
  source_label: string;
  audience: string;
  synthetic: boolean;
  deleted: boolean;
  current_revision: number | null;
  version_id: string | null;
  effective_date: string | null;
  page_count: number | null;
  indexing_state: string | null;
  extraction_error: string | null;
  extraction_warning: string | null;
  chunk_count: number;
  original_filename: string | null;
  updated_at: string | null;
};

export type VersionRecord = {
  id: string;
  revision: number;
  effective_date: string;
  is_current: boolean;
  superseded_at: string | null;
  page_count: number | null;
  indexing_state: string;
  extraction_error: string | null;
  extraction_warning: string | null;
  sha256: string;
  original_filename: string;
  byte_size: number;
  created_at: string;
};

export type ChunkRecord = {
  id: string;
  ordinal: number;
  page_number: number | null;
  section_title: string | null;
  text: string;
  text_sha256: string;
  is_current: boolean;
  instruction_override: boolean;
};

export type VersionText = {
  document: DocumentRecord;
  version: VersionRecord;
  chunks: ChunkRecord[];
};

export type ExamplePrompt = {
  id: string;
  question: string;
  blurb: string;
};

export type Overview = {
  documents: number;
  versions: number;
  categories_in_use: number;
  chunks: number;
  conversations: number;
  categories: Category[];
  recent_documents: DocumentRecord[];
  examples: ExamplePrompt[];
  retrieval: {
    corpus_version: number;
    dense_ready: boolean;
    qdrant_ready: boolean;
    mode: "hybrid" | "sparse";
  };
  demo: boolean;
};

export type SettingsInfo = {
  app_env: string;
  llm_mode: "extractive";
  external_llm_calls: boolean;
  embedding_model: string;
  embedding_dimensions: number;
  embedding_license: string;
  embedding_ready: boolean;
  retrieval: string;
  loopback_only: boolean;
  limitations: string[];
};

export type ReadyInfo = {
  status: "ok" | "degraded" | "unavailable";
  checks: {
    database: { ok: boolean; detail: string | null };
    qdrant: { ok: boolean; detail: string | null };
    embeddings: { ok: boolean; detail: string | null };
  };
};

export type Citation = {
  id: string;
  chunk_id: string | null;
  document_id: string;
  document_version_id: string;
  document_title: string;
  category: string;
  source_label: string;
  revision: number;
  section_title: string | null;
  page_number: number | null;
  snippet: string;
  snippet_sha256: string;
  effective_date: string;
  rank: number;
  rrf_score: number;
  bm25_score: number;
  dense_score: number | null;
};

export type EvidenceThresholds = {
  min_overlap: number;
  min_bm25: number;
  min_cosine: number;
  max_passages: number;
};

export type Evidence = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  revision: number;
  section_title: string | null;
  page_number: number | null;
  bm25_score: number;
  dense_score: number | null;
  rrf_score: number;
  overlap: number;
  used: boolean;
  rejected_reason: string | null;
  preview: string;
  clears_overlap: boolean;
  clears_bm25: boolean;
  clears_dense: boolean;
  clears_abstention_gate: boolean;
};

export type SupersededHint = {
  document_id: string;
  document_version_id: string;
  document_title: string;
  revision: number;
  effective_date: string;
  current_revision: number | null;
  note: string;
};

export type Message = {
  id: string;
  role: string;
  content: string;
  mode: string | null;
  retrieval_mode: string | null;
  contradictory: boolean;
  conflict_note: string | null;
  notice: string | null;
  dense_available: boolean | null;
  preamble: string | null;
  abstention_reason: string | null;
  citations: Citation[];
  evidence: Evidence[];
  superseded: SupersededHint[];
  evidence_thresholds: EvidenceThresholds | null;
  created_at: string;
};

export type QueryResponse = Message & { conversation_id: string };

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  messages: Message[];
};
