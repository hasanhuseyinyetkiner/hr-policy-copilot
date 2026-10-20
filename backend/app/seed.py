"""Load the synthetic corpus described by data/demo/manifest.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.demo_files import build_docx, build_text_pdf
from app.models import Document
from app.services.ingestion import UploadMeta, ingest_replacement, ingest_upload
from app.services.maintenance import assert_demo, wipe_business_data
from app.services.present import overview


class DemoVersionSpec(BaseModel):
    revision: int
    effective_date: date
    filename: str
    format: Literal["txt", "html", "pdf", "docx"]


class DemoDocumentSpec(BaseModel):
    slug: str
    title: str
    category: str
    source_label: str
    audience: str = "staff"
    versions: list[DemoVersionSpec] = Field(min_length=1)


def seed_demo(app_state) -> dict:
    assert_demo(app_state)
    wipe_business_data(app_state)
    directory = Path(app_state.settings.demo_data_dir)
    specs = load_manifest(directory)
    for spec in specs:
        for index, version in enumerate(spec.versions):
            filename, content = render_version(directory, version)
            if index == 0:
                ingest_upload(
                    app_state,
                    filename,
                    content,
                    UploadMeta(
                        title=spec.title,
                        category=spec.category,
                        source_label=spec.source_label,
                        audience=spec.audience,
                        effective_date=version.effective_date,
                        slug=spec.slug,
                    ),
                )
                continue
            session = app_state.session_factory()
            try:
                document = session.scalar(
                    select(Document).where(
                        Document.slug == spec.slug,
                        Document.deleted_at.is_(None),
                    )
                )
                if document is None:
                    raise RuntimeError(f"Seed document {spec.slug} was not created.")
                document_id = document.id
            finally:
                session.close()
            ingest_replacement(
                app_state,
                document_id,
                filename,
                content,
                effective_date=version.effective_date,
                title=spec.title,
            )
    session = app_state.session_factory()
    try:
        return overview(session, app_state).model_dump(mode="json")
    finally:
        session.close()


def load_manifest(directory: Path) -> list[DemoDocumentSpec]:
    payload = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return [DemoDocumentSpec.model_validate(item) for item in payload]


def render_version(directory: Path, spec: DemoVersionSpec) -> tuple[str, bytes]:
    source_path = directory / spec.filename
    text = source_path.read_text(encoding="utf-8")
    if "SYNTHETIC" not in text:
        raise RuntimeError(f"{spec.filename} is missing the SYNTHETIC marker.")
    if spec.format == "pdf":
        return f"{source_path.stem}.pdf", build_text_pdf(text)
    if spec.format == "docx":
        return f"{source_path.stem}.docx", build_docx(text)
    return spec.filename, text.encode("utf-8")
