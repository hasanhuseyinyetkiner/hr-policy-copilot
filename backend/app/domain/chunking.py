"""Section-aware chunking."""

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(?:#{1,3}\s+\S|\d+\.\s+\S)")


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    page_number: int | None
    section_title: str | None
    text: str


def split_text(text: str, max_chars: int = 900, overlap: int = 80) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    parts: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        if end < len(cleaned):
            space = cleaned.rfind(" ", start + max_chars // 2, end)
            if space != -1:
                end = space
        part = cleaned[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(cleaned):
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return parts


def _take_buffer(
    buffer: list[str],
    page_number: int,
    section: str | None,
    blocks: list[tuple[int, str | None, str]],
) -> list[str]:
    text = "\n".join(line for line in buffer if line).strip()
    if text:
        blocks.append((page_number, section, text))
    return []


def chunk_pages(pages: list[tuple[int, str]], *, max_chars: int = 900) -> list[ChunkDraft]:
    blocks: list[tuple[int, str | None, str]] = []
    for page_number, raw in pages:
        section: str | None = "Preamble"
        buffer: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _HEADING.match(stripped):
                buffer = _take_buffer(buffer, page_number, section, blocks)
                section = stripped.lstrip("#").strip()
                continue
            buffer.append(stripped)
        _take_buffer(buffer, page_number, section, blocks)

    drafts: list[ChunkDraft] = []
    for page_number, section, text in blocks:
        for part in split_text(text, max_chars=max_chars):
            drafts.append(
                ChunkDraft(
                    ordinal=len(drafts),
                    page_number=page_number,
                    section_title=section,
                    text=part,
                )
            )
    return drafts
