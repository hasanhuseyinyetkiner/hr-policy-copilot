"""Download the local embedding model. Run with the backend environment."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.download_model import main  # noqa: E402

if __name__ == "__main__":
    main()
