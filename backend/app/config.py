"""Runtime configuration.

Local development uses SQLite and on-disk Qdrant. Compose points the same
settings at PostgreSQL and the Qdrant server.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]


def sqlite_url(path: Path) -> str:
    return "sqlite:///" + path.resolve().as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "demo"
    api_host: str = "127.0.0.1"
    api_port: int = 8101
    allow_network_bind: bool = False

    database_url: str = Field(
        default_factory=lambda: sqlite_url(REPO_ROOT / "data" / "app.sqlite3")
    )
    qdrant_mode: str = "local"
    qdrant_path: str = Field(default_factory=lambda: str(REPO_ROOT / "data" / "qdrant"))
    qdrant_url: str = "http://127.0.0.1:6301"
    qdrant_collection: str = "policy_chunks"
    qdrant_wait: bool = False

    embedding_backend: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    model_dir: str = Field(default_factory=lambda: str(REPO_ROOT / "models" / "all-MiniLM-L6-v2"))
    hf_hub_offline: bool = True

    demo_data_dir: str = Field(default_factory=lambda: str(REPO_ROOT / "data" / "demo"))
    upload_dir: str = Field(default_factory=lambda: str(REPO_ROOT / "data" / "uploads"))
    seed_on_startup: bool = True

    upload_max_bytes: int = 8 * 1024 * 1024
    parse_timeout_seconds: int = 20
    parse_page_cap: int = 40
    parse_text_cap: int = 500_000
    docx_uncompressed_cap: int = 50 * 1024 * 1024
    docx_ratio_cap: float = 100.0

    stale_job_seconds: int = 300
    ingest_debug_sleep_seconds: float = 0.0
    fault_inject: str = ""

    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rrf_k: int = 60
    evidence_min_overlap: int = 3
    evidence_min_bm25: float = 1.0
    evidence_min_cosine: float = 0.55
    retrieval_candidate_limit: int = 30
    max_passages: int = 4

    cors_origins: str = "http://127.0.0.1:5101,http://localhost:5101"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def get_settings() -> Settings:
    return Settings()


def enforce_loopback(settings: Settings) -> None:
    host = settings.api_host.strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"} and not settings.allow_network_bind:
        raise RuntimeError("Refusing to bind a non-loopback host without ALLOW_NETWORK_BIND=true.")
