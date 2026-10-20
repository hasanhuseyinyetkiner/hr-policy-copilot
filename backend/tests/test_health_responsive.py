"""Prove /health stays responsive while ingestion work is off the event loop."""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from tests.conftest import make_settings


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_health_stays_responsive_during_ingest(tmp_path: Path) -> None:
    port = _free_port()
    settings = make_settings(
        tmp_path,
        api_port=port,
        ingest_debug_sleep_seconds=2.5,
    )
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "demo",
            "API_HOST": "127.0.0.1",
            "API_PORT": str(port),
            "ALLOW_NETWORK_BIND": "false",
            "DATABASE_URL": settings.database_url,
            "QDRANT_MODE": "local",
            "QDRANT_PATH": settings.qdrant_path,
            "QDRANT_URL": "http://127.0.0.1:9",
            "EMBEDDING_BACKEND": "hash",
            "MODEL_DIR": settings.model_dir,
            "HF_HUB_OFFLINE": "1",
            "DEMO_DATA_DIR": settings.demo_data_dir,
            "UPLOAD_DIR": settings.upload_dir,
            "SEED_ON_STARTUP": "false",
            "INGEST_DEBUG_SLEEP_SECONDS": "2.5",
            "PARSE_TIMEOUT_SECONDS": "20",
        }
    )
    backend = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "app"],
        cwd=str(backend),
        env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.perf_counter() + 30
        while time.perf_counter() < deadline:
            try:
                probe = httpx.get(f"{base}/health", timeout=1)
                if probe.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            raise AssertionError("server did not start")

        result: dict[str, object] = {}

        def post_document() -> None:
            started = time.perf_counter()
            response = httpx.post(
                f"{base}/api/documents",
                files={
                    "file": (
                        "slow.txt",
                        b"SYNTHETIC\n\n1. Slow\nThe slow color code is mist-blue.\n",
                        "text/plain",
                    )
                },
                data={
                    "title": "Slow Note",
                    "category": "company_policy",
                    "source_label": "Synthetic — test upload",
                    "audience": "staff",
                    "effective_date": "2026-01-01",
                },
                timeout=30,
            )
            result["status"] = response.status_code
            result["elapsed"] = time.perf_counter() - started

        worker = threading.Thread(target=post_document)
        worker.start()
        time.sleep(0.7)
        assert worker.is_alive()
        health_started = time.perf_counter()
        health = httpx.get(f"{base}/health", timeout=1)
        health_elapsed = time.perf_counter() - health_started
        assert health.status_code == 200
        assert health_elapsed < 0.75
        worker.join(timeout=15)
        assert result["status"] == 201
        assert float(result["elapsed"]) >= 2.0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], check=False)
