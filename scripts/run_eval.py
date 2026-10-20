"""Run retrieval eval against a live app or an ephemeral TestClient seed.

Usage (from repo root, with backend deps):

  cd backend && uv run python ../scripts/run_eval.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings, sqlite_url  # noqa: E402
from app.eval_metrics import evaluate_all, format_markdown  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    out_dir = REPO / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hr-eval-") as tmp:
        tmp_path = Path(tmp)
        settings = Settings(
            app_env="demo",
            api_host="127.0.0.1",
            allow_network_bind=False,
            database_url=sqlite_url(tmp_path / "eval.sqlite3"),
            qdrant_mode="local",
            qdrant_path=str(tmp_path / "qdrant"),
            embedding_backend="hash",
            model_dir=str(tmp_path / "missing-model"),
            demo_data_dir=str(REPO / "data" / "demo"),
            upload_dir=str(tmp_path / "uploads"),
            seed_on_startup=False,
            qdrant_wait=False,
        )
        application = create_app(settings)
        with TestClient(application) as client:
            assert client.post("/api/demo/reset").status_code == 200
            report = evaluate_all(client)
    json_path = out_dir / "EVAL_RESULTS.json"
    md_path = out_dir / "EVAL.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(format_markdown(report), encoding="utf-8")
    print(format_markdown(report))
    print(f"Wrote {json_path.relative_to(REPO)} and {md_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
