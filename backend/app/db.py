"""Engine, migrations, and reference data."""

from collections.abc import Iterator
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import BACKEND_ROOT
from app.models import Category, CorpusState

CATEGORY_ROWS: tuple[tuple[str, str, str], ...] = (
    (
        "company_policy",
        "Company policy",
        "Internal policy of the fictional company Northwind People Ops. Not legal advice.",
    ),
    (
        "regulatory_briefing",
        "Regulatory briefing",
        "Synthetic orientation note. Not a statute, not official guidance, and not legal advice.",
    ),
)

BUSINESS_TABLES: tuple[str, ...] = (
    "citations",
    "messages",
    "conversations",
    "chunk_terms",
    "chunks",
    "ingestion_jobs",
    "document_versions",
    "documents",
    "corpus_state",
)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def run_migrations(url: str) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


def ensure_reference_data(session: Session) -> None:
    for key, label, description in CATEGORY_ROWS:
        if session.get(Category, key) is None:
            session.add(Category(key=key, label=label, description=description))
    if session.get(CorpusState, 1) is None:
        session.add(CorpusState(id=1, corpus_version=0, n_docs=0, total_tokens=0, avgdl=0.0))
    session.commit()


def database_ok(engine: Engine) -> tuple[bool, str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, exc.__class__.__name__


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def bump_corpus_state(session: Session) -> int:
    from sqlalchemy import func

    from app.models import Chunk

    n_docs = int(
        session.scalar(select(func.count()).select_from(Chunk).where(Chunk.is_current.is_(True)))
        or 0
    )
    total_tokens = int(
        session.scalar(
            select(func.coalesce(func.sum(Chunk.token_count), 0)).where(Chunk.is_current.is_(True))
        )
        or 0
    )
    state = session.get(CorpusState, 1)
    if state is None:
        state = CorpusState(id=1, corpus_version=0, n_docs=0, total_tokens=0, avgdl=0.0)
        session.add(state)
    state.corpus_version += 1
    state.n_docs = n_docs
    state.total_tokens = total_tokens
    state.avgdl = (total_tokens / n_docs) if n_docs else 0.0
    return state.corpus_version
