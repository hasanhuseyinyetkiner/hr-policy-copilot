"""Qdrant adapter. Local path mode for dev/tests; HTTP for Compose."""

from __future__ import annotations

import logging
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams

from app.config import Settings

logger = logging.getLogger(__name__)

VECTOR_FAILURE = "vector_index_unavailable"


class VectorIndexError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = VECTOR_FAILURE
        self.message = message


def connect_qdrant(settings: Settings) -> QdrantClient:
    if settings.qdrant_mode == "local":
        path = Path(settings.qdrant_path)
        path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(path))
    return QdrantClient(url=settings.qdrant_url, timeout=3, check_compatibility=False)


def close_qdrant(client: QdrantClient | None) -> None:
    if client is None:
        return
    close = getattr(client, "close", None)
    if callable(close):
        close()


def ensure_collection(client: QdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection
    if _collection_exists(client, name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=settings.embedding_dimensions,
            distance=Distance.COSINE,
        ),
    )


def reset_collection(client: QdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection
    if _collection_exists(client, name):
        client.delete_collection(name)
    ensure_collection(client, settings)


def upsert_points(
    client: QdrantClient, settings: Settings, rows: list[tuple[str, list[float]]]
) -> None:
    if not rows:
        return
    ensure_collection(client, settings)
    points = [
        PointStruct(id=chunk_id, vector=vector, payload={"chunk_id": chunk_id})
        for chunk_id, vector in rows
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)


def delete_points(client: QdrantClient, settings: Settings, point_ids: list[str]) -> None:
    if not point_ids or not _collection_exists(client, settings.qdrant_collection):
        return
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=PointIdsList(points=point_ids),
        wait=True,
    )


def search_points(
    client: QdrantClient,
    settings: Settings,
    vector: list[float],
    limit: int,
) -> list[tuple[str, float]]:
    if not _collection_exists(client, settings.qdrant_collection):
        return []
    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    found: list[tuple[str, float]] = []
    for point in response.points:
        payload = point.payload or {}
        chunk_id = str(payload.get("chunk_id") or point.id)
        found.append((chunk_id, float(point.score)))
    return found


def list_point_ids(client: QdrantClient, settings: Settings) -> set[str]:
    if not _collection_exists(client, settings.qdrant_collection):
        return set()
    found: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.qdrant_collection,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        found.update(str(point.id) for point in points)
        if offset is None:
            break
    return found


def open_qdrant(settings: Settings) -> tuple[QdrantClient | None, str | None]:
    client: QdrantClient | None = None
    try:
        client = connect_qdrant(settings)
        if settings.qdrant_wait:
            last_error: Exception | None = None
            for _ in range(30):
                try:
                    client.get_collections()
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    import time

                    time.sleep(2)
            if last_error is not None:
                raise last_error
        ensure_collection(client, settings)
        return client, None
    except Exception as exc:  # noqa: BLE001
        logger.info("qdrant open failed: %s", exc.__class__.__name__)
        close_qdrant(client)
        return None, exc.__class__.__name__


def qdrant_status(client: QdrantClient | None, settings: Settings) -> tuple[bool, str | None]:
    if client is None:
        return False, "client_not_connected"
    try:
        ensure_collection(client, settings)
        return True, settings.qdrant_mode
    except Exception as exc:  # noqa: BLE001
        logger.info("qdrant status failed: %s", exc.__class__.__name__)
        return False, exc.__class__.__name__


def _collection_exists(client: QdrantClient, name: str) -> bool:
    exists = getattr(client, "collection_exists", None)
    if callable(exists):
        return bool(exists(collection_name=name))
    try:
        client.get_collection(name)
        return True
    except Exception:  # noqa: BLE001
        return False
