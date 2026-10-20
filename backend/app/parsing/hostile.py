"""Reject hostile Office Open XML packages before they are parsed."""

import zipfile
from pathlib import Path


class HostileFile(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def inspect_docx_zip(path: Path, *, uncompressed_cap: int, ratio_cap: float) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise HostileFile("invalid_docx", "The DOCX file is not a valid zip package.") from exc
    with archive:
        infos = archive.infolist()
        uncompressed = sum(info.file_size for info in infos)
        compressed = sum(info.compress_size for info in infos)
    if uncompressed > uncompressed_cap:
        raise HostileFile(
            "docx_uncompressed_cap",
            "The DOCX package uncompressed size exceeds the 50 MB cap.",
        )
    if uncompressed > 0 and (compressed == 0 or uncompressed / compressed > ratio_cap):
        raise HostileFile(
            "docx_compression_ratio",
            "The DOCX package compression ratio exceeds the allowed limit.",
        )


def has_unterminated_inline_image(data: bytes) -> bool:
    """True when a PDF content stream has an inline image ``BI``/``ID`` without ``EI``."""
    index = 0
    while index < len(data):
        start = _find_operator(data, b"BI", index)
        if start is None:
            return False
        image_id = _find_operator(data, b"ID", start + 2)
        endstream = data.find(b"endstream", start)
        if image_id is None:
            return False
        region_end = endstream if endstream != -1 else len(data)
        if image_id > region_end:
            index = start + 2
            continue
        header = data[start:image_id]
        if b"/W" in header and b"/BPC" in header:
            after = data[image_id + 2 : region_end]
            if _find_operator(after, b"EI", 0) is None:
                return True
        index = image_id + 2
    return False


def _find_operator(data: bytes, token: bytes, start: int) -> int | None:
    index = start
    while True:
        found = data.find(token, index)
        if found == -1:
            return None
        before_ok = found == 0 or data[found - 1] in b"\n\r \t"
        after = found + len(token)
        after_ok = after >= len(data) or data[after] in b"\n\r \t"
        if before_ok and after_ok:
            return found
        index = found + 1
