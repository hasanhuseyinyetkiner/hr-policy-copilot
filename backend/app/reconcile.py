"""Compare Qdrant points with current database chunks and repair the gap."""

from sqlalchemy import select

from app.models import Chunk
from app.services.embeddings import embed_texts
from app.services.vectors import delete_points, list_point_ids, upsert_points


def reconcile_index(app_state) -> dict[str, object]:
    if app_state.qdrant is None:
        return {"deleted": 0, "embedded": 0, "current": 0, "error": "qdrant_unavailable"}
    session = app_state.session_factory()
    try:
        chunks = list(session.scalars(select(Chunk).where(Chunk.is_current.is_(True))).all())
    finally:
        session.close()
    current = {chunk.id: chunk for chunk in chunks}
    existing = list_point_ids(app_state.qdrant, app_state.settings)
    stale = sorted(existing - set(current))
    missing_ids = [chunk_id for chunk_id in current if chunk_id not in existing]
    if stale:
        delete_points(app_state.qdrant, app_state.settings, stale)
    embedded = 0
    error = None
    if missing_ids:
        try:
            ordered = [current[chunk_id] for chunk_id in missing_ids]
            vectors = embed_texts([chunk.text for chunk in ordered], app_state.settings)
            upsert_points(
                app_state.qdrant,
                app_state.settings,
                list(zip(missing_ids, vectors, strict=True)),
            )
            embedded = len(missing_ids)
        except Exception as exc:  # noqa: BLE001
            error = exc.__class__.__name__
    return {
        "deleted": len(stale),
        "embedded": embedded,
        "current": len(current),
        "error": error,
    }
