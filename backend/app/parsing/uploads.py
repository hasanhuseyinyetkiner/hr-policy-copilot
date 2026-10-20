"""Upload checks that do not require a parser."""

import hashlib
import re
from pathlib import Path

from app.config import Settings
from app.errors import AppError

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".htm"}

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
}


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def safe_original_name(filename: str, extension: str) -> str:
    name = Path(filename or "upload").name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:180].strip(" .")
    if not name:
        name = "upload"
    if not name.lower().endswith(extension):
        stem = Path(name).stem or "upload"
        name = f"{stem}{extension}"
    return name


def validate_upload(filename: str, content: bytes, settings: Settings) -> str:
    extension = extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise AppError(
            "unsupported_extension",
            "Upload a PDF, DOCX, TXT, or HTML file.",
            400,
        )
    if len(content) == 0:
        raise AppError("empty_file", "The uploaded file is empty.", 400)
    if len(content) > settings.upload_max_bytes:
        raise AppError(
            "file_too_large",
            "The file exceeds the upload size cap.",
            400,
        )
    if not _magic_matches(extension, content):
        raise AppError(
            "mime_mismatch",
            "The file contents do not match its extension.",
            400,
        )
    return extension


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _magic_matches(extension: str, content: bytes) -> bool:
    if extension == ".pdf":
        return content.startswith(b"%PDF")
    if extension == ".docx":
        return content.startswith(b"PK\x03\x04")
    if extension in {".txt", ".html", ".htm"}:
        sample = content[:4096]
        if b"\x00" in sample:
            return False
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return False
        if extension in {".html", ".htm"} and b"<" not in content[:8192].lower():
            return False
        return True
    return False
