"""Download the embedding model into the gitignored local cache."""

import os
from pathlib import Path

from app.config import get_settings


def main() -> None:
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    settings = get_settings()
    target = Path(settings.model_dir)
    target.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=settings.embedding_model, local_dir=str(target))
    print(f"model ready at {target}")


if __name__ == "__main__":
    main()
