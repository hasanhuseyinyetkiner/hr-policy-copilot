"""Embedding providers.

The demo backend is ``sentence-transformers/all-MiniLM-L6-v2`` loaded from a
local directory. ``hash`` is a deterministic test double and is never the
default. Model load and encoding stay off the API event loop because callers
use a worker thread.
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
from pathlib import Path

from app.config import Settings
from app.domain.tokenize import tokenize

_LOCK = threading.Lock()
_MODEL = None
_MODEL_DIR: str | None = None


class EmbeddingsUnavailable(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = "embeddings_unavailable"
        self.message = message


def model_status(settings: Settings) -> tuple[bool, str]:
    if settings.embedding_backend == "hash":
        return True, "deterministic hash embedder"
    path = Path(settings.model_dir)
    if (path / "modules.json").is_file():
        return True, settings.embedding_model
    return False, f"model files not found at {settings.model_dir}"


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedding_backend == "hash":
        return [_hash_vector(text, settings.embedding_dimensions) for text in texts]
    model = _load_local_model(settings)
    encoded = model.encode(
        list(texts),
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [vector.tolist() for vector in encoded]


def _hash_vector(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    tokens = tokenize(text) or ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _load_local_model(settings: Settings):
    global _MODEL, _MODEL_DIR
    ready, detail = model_status(settings)
    if not ready:
        raise EmbeddingsUnavailable(detail)
    with _LOCK:
        if _MODEL is not None and _MODEL_DIR == settings.model_dir:
            return _MODEL
        if settings.hf_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(
            settings.model_dir,
            device="cpu",
            local_files_only=True,
        )
        _MODEL_DIR = settings.model_dir
        return _MODEL
