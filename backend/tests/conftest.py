"""Shared fixtures. Tests use SQLite unless PYTEST_USE_ENV_DB=1."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings, sqlite_url
from app.main import create_app


def make_settings(tmp_path: Path, **overrides) -> Settings:
    if (
        os.environ.get("PYTEST_USE_ENV_DB") == "1"
        and os.environ.get("DATABASE_URL", "").startswith("postgresql")
        and "database_url" not in overrides
    ):
        database_url = os.environ["DATABASE_URL"]
    else:
        database_url = sqlite_url(tmp_path / "test.sqlite3")
    values = {
        "app_env": "demo",
        "api_host": "127.0.0.1",
        "api_port": 8101,
        "allow_network_bind": False,
        "database_url": database_url,
        "qdrant_mode": "local",
        "qdrant_path": str(tmp_path / "qdrant"),
        "embedding_backend": "hash",
        "model_dir": str(tmp_path / "missing-model"),
        "hf_hub_offline": True,
        "demo_data_dir": str(REPO_ROOT / "data" / "demo"),
        "upload_dir": str(tmp_path / "uploads"),
        "seed_on_startup": False,
        "ingest_debug_sleep_seconds": 0,
        "fault_inject": "",
        "parse_timeout_seconds": 20,
        "qdrant_wait": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client(tmp_path: Path):
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as test_client:
        wiped = test_client.post("/api/demo/delete-all")
        assert wiped.status_code == 200, wiped.text
        yield test_client


@pytest.fixture
def seeded(client: TestClient):
    response = client.post("/api/demo/reset")
    assert response.status_code == 200, response.text
    return client
