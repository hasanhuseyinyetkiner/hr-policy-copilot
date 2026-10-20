"""Run retrieval eval against an ephemeral TestClient seed.

Usage (from repo root, with backend deps):

  cd backend && uv run python ../scripts/run_eval.py
  cd backend && uv run python ../scripts/run_eval.py --backend local
  cd backend && uv run python ../scripts/run_eval.py --backend hash --modes hybrid,dense,sparse

Defaults write fixture (hash) results to docs/EVAL_RESULTS.json and docs/EVAL.md.
MiniLM runs write docs/EVAL_RESULTS_MINILM.json and docs/EVAL_MINILM.md —
they never overwrite the hash fixture table.
"""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HR Policy Copilot retrieval eval.")
    parser.add_argument(
        "--backend",
        choices=("hash", "local"),
        default="hash",
        help="Embedding backend: hash (fixture/default) or local (MiniLM on disk).",
    )
    parser.add_argument(
        "--modes",
        default="hybrid,dense,sparse",
        help="Comma-separated retrieval_preference values (hybrid,dense,sparse).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modes = tuple(item.strip() for item in args.modes.split(",") if item.strip())
    if not modes:
        print("No retrieval modes specified.", file=sys.stderr)
        return 2
    for mode in modes:
        if mode not in {"hybrid", "dense", "sparse"}:
            print(f"Invalid mode: {mode}", file=sys.stderr)
            return 2

    out_dir = REPO / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = REPO / "models" / "all-MiniLM-L6-v2"

    if args.backend == "local" and not model_dir.is_dir():
        print(
            f"MiniLM model directory missing: {model_dir}\n"
            "Download first: cd backend && uv run python -m app.download_model\n"
            "Not inventing MiniLM scores — aborting.",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="hr-eval-") as tmp:
        tmp_path = Path(tmp)
        settings = Settings(
            app_env="demo",
            api_host="127.0.0.1",
            allow_network_bind=False,
            database_url=sqlite_url(tmp_path / "eval.sqlite3"),
            qdrant_mode="local",
            qdrant_path=str(tmp_path / "qdrant"),
            embedding_backend=args.backend,
            model_dir=str(model_dir if args.backend == "local" else tmp_path / "missing-model"),
            demo_data_dir=str(REPO / "data" / "demo"),
            upload_dir=str(tmp_path / "uploads"),
            seed_on_startup=False,
            qdrant_wait=False,
            hf_hub_offline=True,
        )
        application = create_app(settings)
        with TestClient(application) as client:
            assert client.post("/api/demo/reset").status_code == 200
            report = evaluate_all(
                client,
                modes=modes,
                embedding_backend=args.backend,
            )

    if args.backend == "hash":
        json_path = out_dir / "EVAL_RESULTS.json"
        md_path = out_dir / "EVAL.md"
    else:
        json_path = out_dir / "EVAL_RESULTS_MINILM.json"
        md_path = out_dir / "EVAL_MINILM.md"

    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(format_markdown(report), encoding="utf-8")
    print(format_markdown(report))
    print(f"Wrote {json_path.relative_to(REPO)} and {md_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
