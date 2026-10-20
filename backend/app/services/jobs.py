"""Ingestion jobs and the startup reaper."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import as_utc, utcnow
from app.models import DocumentVersion, IngestionJob


def reap_stale_jobs(session: Session, stale_seconds: int) -> int:
    cutoff = utcnow() - timedelta(seconds=stale_seconds)
    jobs = session.scalars(select(IngestionJob).where(IngestionJob.status == "RUNNING")).all()
    reaped = 0
    for job in jobs:
        if job.heartbeat_at is None or as_utc(job.heartbeat_at) >= cutoff:
            continue
        job.status = "FAILED"
        job.error = "stale heartbeat: worker did not finish before the startup reaper ran"
        job.finished_at = utcnow()
        version = session.get(DocumentVersion, job.document_version_id)
        if version is not None and version.indexing_state == "pending":
            version.indexing_state = "failed"
            version.extraction_error = job.error
        reaped += 1
    if reaped:
        session.commit()
    return reaped


def mark_job(
    session: Session,
    job_id: str,
    status: str,
    error: str | None,
) -> None:
    job = session.get(IngestionJob, job_id)
    if job is None:
        return
    now = utcnow()
    job.status = status
    job.error = error
    job.heartbeat_at = now
    job.finished_at = now if status in {"SUCCEEDED", "FAILED"} else job.finished_at
    session.commit()
