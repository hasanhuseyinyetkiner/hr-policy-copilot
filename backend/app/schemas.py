"""API schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    error: str
    code: str
    detail: object | None = None


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"


class CheckOut(BaseModel):
    ok: bool
    detail: str | None = None


class ReadyChecks(BaseModel):
    database: CheckOut
    qdrant: CheckOut
    embeddings: CheckOut


class ReadyOut(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    checks: ReadyChecks


class CategoryOut(BaseModel):
    key: str
    label: str
    description: str
    document_count: int


class DocumentOut(BaseModel):
    id: str
    title: str
    policy_id: str | None = None
    category: str
    category_label: str
    source_label: str
    audience: str
    synthetic: bool
    deleted: bool
    current_revision: int | None
    version_id: str | None
    effective_date: date | None
    page_count: int | None
    indexing_state: str | None
    extraction_error: str | None
    extraction_warning: str | None
    chunk_count: int
    original_filename: str | None
    updated_at: datetime | None


class VersionOut(BaseModel):
    id: str
    revision: int
    effective_date: date
    is_current: bool
    superseded_at: datetime | None
    page_count: int | None
    indexing_state: str
    extraction_error: str | None
    extraction_warning: str | None
    sha256: str
    original_filename: str
    byte_size: int
    created_at: datetime


class ChunkOut(BaseModel):
    id: str
    ordinal: int
    page_number: int | None
    section_title: str | None
    text: str
    text_sha256: str
    is_current: bool
    instruction_override: bool


class VersionTextOut(BaseModel):
    document: DocumentOut
    version: VersionOut
    chunks: list[ChunkOut]


class ExamplePrompt(BaseModel):
    id: str
    question: str
    blurb: str


class RetrievalStatus(BaseModel):
    corpus_version: int
    dense_ready: bool
    qdrant_ready: bool
    mode: Literal["hybrid", "sparse", "dense"]


class OverviewOut(BaseModel):
    documents: int
    versions: int
    categories_in_use: int
    chunks: int
    conversations: int
    categories: list[CategoryOut]
    recent_documents: list[DocumentOut]
    examples: list[ExamplePrompt]
    retrieval: RetrievalStatus
    demo: bool


class SettingsOut(BaseModel):
    app_env: str
    llm_mode: Literal["extractive"]
    external_llm_calls: bool
    embedding_model: str
    embedding_dimensions: int
    embedding_license: str
    embedding_ready: bool
    retrieval: str
    loopback_only: bool
    limitations: list[str]


class CitationOut(BaseModel):
    id: str
    chunk_id: str | None
    document_id: str
    document_version_id: str
    document_title: str
    category: str
    source_label: str
    revision: int
    section_title: str | None
    page_number: int | None
    snippet: str
    snippet_sha256: str
    effective_date: date
    rank: int
    rrf_score: float
    bm25_score: float
    dense_score: float | None


class EvidenceThresholdsOut(BaseModel):
    min_overlap: int
    min_bm25: float
    min_cosine: float
    max_passages: int


class EvidenceOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    revision: int
    section_title: str | None
    page_number: int | None
    bm25_score: float
    dense_score: float | None
    rrf_score: float
    overlap: int
    used: bool
    rejected_reason: str | None
    preview: str
    clears_overlap: bool = False
    clears_bm25: bool = False
    clears_dense: bool = False
    clears_abstention_gate: bool = False


class SupersededHint(BaseModel):
    document_id: str
    document_version_id: str
    document_title: str
    revision: int
    effective_date: date
    current_revision: int | None
    note: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    mode: str | None = None
    retrieval_mode: str | None = None
    contradictory: bool = False
    conflict_note: str | None = None
    notice: str | None = None
    dense_available: bool | None = None
    preamble: str | None = None
    abstention_reason: str | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    superseded: list[SupersededHint] = Field(default_factory=list)
    evidence_thresholds: EvidenceThresholdsOut | None = None
    created_at: datetime


class QueryOut(MessageOut):
    conversation_id: str


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    categories: list[str] | None = None
    audience: str = "staff"
    retrieval_preference: Literal["hybrid", "dense", "sparse"] = "hybrid"


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    message_count: int


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: list[MessageOut]


class MessageExtras(BaseModel):
    preamble: str
    abstention_reason: str | None = None
    evidence: list[EvidenceOut] = Field(default_factory=list)
    superseded: list[SupersededHint] = Field(default_factory=list)
    evidence_thresholds: EvidenceThresholdsOut | None = None
