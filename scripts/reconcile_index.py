"""Repair the vector index from the database. Run with the backend environment."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import ensure_reference_data, make_engine, make_session_factory, run_migrations  # noqa: E402
from app.reconcile import reconcile_index  # noqa: E402
from app.services.vectors import close_qdrant, open_qdrant  # noqa: E402


def main() -> None:
    settings = get_settings()
    run_migrations(settings.database_url)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    session = factory()
    try:
        ensure_reference_data(session)
    finally:
        session.close()
    client, error = open_qdrant(settings)
    state = SimpleNamespace(
        settings=settings,
        session_factory=factory,
        qdrant=client,
        qdrant_error=error,
    )
    try:
        print(json.dumps(reconcile_index(state)))
    finally:
        close_qdrant(client)
        engine.dispose()


if __name__ == "__main__":
    main()
