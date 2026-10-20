"""Text extraction for PDF, DOCX, HTML, and plain text."""

import re
from pathlib import Path

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

from app.parsing.hostile import has_unterminated_inline_image


class ExtractError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def extract_document(
    path: Path,
    extension: str,
    *,
    page_cap: int,
    text_cap: int,
) -> tuple[list[tuple[int, str]], str | None]:
    if extension == ".pdf":
        return _extract_pdf(path, page_cap=page_cap, text_cap=text_cap)
    if extension == ".docx":
        return _extract_docx(path, text_cap=text_cap)
    if extension in {".html", ".htm"}:
        return _extract_html(path, text_cap=text_cap)
    if extension == ".txt":
        return _extract_text(path, text_cap=text_cap)
    raise ExtractError("unsupported_extension", "This file type is not supported.")


_HEADING_BREAK = re.compile(r"[ \t]+(?=\d+\.\s+\S)")


def _restore_heading_lines(text: str) -> str:
    return _HEADING_BREAK.sub("\n", text)


def _cap_pages(
    pages: list[tuple[int, str]],
    *,
    text_cap: int,
) -> tuple[list[tuple[int, str]], str | None]:
    kept: list[tuple[int, str]] = []
    total = 0
    truncated = False
    for page_number, text in pages:
        remaining = text_cap - total
        if remaining <= 0:
            truncated = True
            break
        if len(text) > remaining:
            kept.append((page_number, text[:remaining]))
            truncated = True
            break
        kept.append((page_number, text))
        total += len(text)
    warning = "Extracted text was truncated at the size cap." if truncated else None
    return kept, warning


def _extract_pdf(
    path: Path, *, page_cap: int, text_cap: int
) -> tuple[list[tuple[int, str]], str | None]:
    data = path.read_bytes()
    if has_unterminated_inline_image(data):
        raise ExtractError(
            "hostile_pdf",
            "The PDF contains an unterminated inline image and was rejected.",
        )
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            raise ExtractError("encrypted_pdf", "Encrypted PDFs are not accepted.")
        pages: list[tuple[int, str]] = []
        for index, page in enumerate(reader.pages, start=1):
            if index > page_cap:
                break
            text = _restore_heading_lines(page.extract_text() or "")
            pages.append((index, text))
    except ExtractError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractError("pdf_parse_failed", "The PDF could not be read.") from exc
    if not pages:
        raise ExtractError("empty_document", "No text could be extracted from the PDF.")
    warning = None
    if len(reader.pages) > page_cap:
        warning = f"Only the first {page_cap} pages were indexed."
    kept, cap_warning = _cap_pages(pages, text_cap=text_cap)
    return kept, warning or cap_warning


def _extract_docx(path: Path, *, text_cap: int) -> tuple[list[tuple[int, str]], str | None]:
    try:
        document = Document(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ExtractError("docx_parse_failed", "The DOCX file could not be read.") from exc
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading") and not text[0].isdigit():
            lines.append(f"1. {text}")
        else:
            lines.append(text)
    joined = "\n".join(lines)
    if not joined.strip():
        raise ExtractError("empty_document", "No text could be extracted from the DOCX file.")
    return _cap_pages([(1, joined)], text_cap=text_cap)


def _extract_html(path: Path, *, text_cap: int) -> tuple[list[tuple[int, str]], str | None]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = element.get_text(" ", strip=True)
        if text:
            lines.append(text)
    if not lines:
        text = soup.get_text("\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)
    if not joined.strip():
        raise ExtractError("empty_document", "No text could be extracted from the HTML file.")
    return _cap_pages([(1, joined)], text_cap=text_cap)


def _extract_text(path: Path, *, text_cap: int) -> tuple[list[tuple[int, str]], str | None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise ExtractError("empty_document", "The text file is empty.")
    return _cap_pages([(1, text)], text_cap=text_cap)
