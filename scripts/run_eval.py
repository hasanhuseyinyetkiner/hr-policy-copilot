"""Run retrieval eval against an ephemeral TestClient seed.

Usage (from repo root, with backend deps):

  cd backend && uv run python ../scripts/run_eval.py
  cd backend && uv run python ../scripts/run_eval.py --backend local
  cd backend && uv run python ../scripts/run_eval.py --backend hash --modes hybrid,dense,sparse
  cd backend && uv run python ../scripts/run_eval.py --dataset heldout/v1

Defaults write fixture (hash) results to docs/EVAL_RESULTS.json.
MiniLM runs write docs/EVAL_RESULTS_MINILM.json — they never overwrite the hash fixture.
The former held-out v1 writes docs/EVAL_RESULTS_DEVELOPMENT_V1.json (with a _MINILM suffix when local).
Narrative tables live in docs/EVALUATION.md.

The formerly held-out v1 set is now development regression data. Do not tune thresholds or fusion parameters on it.
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
from app.eval_metrics import (  # noqa: E402
    evaluate_all,
    format_markdown,
    load_eval_rows,
    resolve_eval_path,
)
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
    parser.add_argument(
        "--dataset",
        default="seed",
        help="seed (data/eval/questions.jsonl) or heldout/v1 (formerly held out; now development regression data).",
    )
    return parser.parse_args()


def _artifact_path(dataset_id: str, backend: str) -> Path:
    out_dir = REPO / "docs"
    if dataset_id.startswith("heldout"):
        base = "EVAL_RESULTS_DEVELOPMENT_V1"
    else:
        base = "EVAL_RESULTS"
    if backend == "local":
        if dataset_id.startswith("heldout"):
            return out_dir / f"{base}_MINILM.json"
        return out_dir / "EVAL_RESULTS_MINILM.json"
    return out_dir / f"{base}.json"


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

    try:
        eval_path = resolve_eval_path(args.dataset)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    dataset_id = "heldout-v1" if "heldout" in str(eval_path).replace("\\", "/") else "seed"
    question_set = str(eval_path.relative_to(REPO)).replace("\\", "/")
    rows = load_eval_rows(eval_path)

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
                rows,
                modes=modes,
                embedding_backend=args.backend,
                question_set=question_set,
                dataset_id=dataset_id,
                include_category_breakdown=dataset_id.startswith("heldout"),
            )

    json_path = _artifact_path(dataset_id, args.backend)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(format_markdown(report))
    print(f"Wrote {json_path.relative_to(REPO)} (update docs/EVALUATION.md tables if scores change)")
    if report.get("category_breakdown"):
        print("\nCategory breakdown (primary mode):")
        print(json.dumps(report["category_breakdown"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
