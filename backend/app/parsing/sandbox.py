"""Parent-side parse sandbox."""

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import BACKEND_ROOT, Settings
from app.parsing.hostile import HostileFile, inspect_docx_zip


@dataclass(frozen=True)
class ParseResult:
    pages: list[tuple[int, str]]
    warning: str | None


def parse_in_subprocess(path: Path, extension: str, settings: Settings) -> ParseResult:
    if extension == ".docx":
        inspect_docx_zip(
            path,
            uncompressed_cap=settings.docx_uncompressed_cap,
            ratio_cap=settings.docx_ratio_cap,
        )
    with tempfile.TemporaryDirectory(prefix="hr-parse-") as directory:
        output = Path(directory) / "result.json"
        command = [
            sys.executable,
            "-m",
            "app.parsing.worker",
            str(path),
            str(output),
            extension,
            str(settings.parse_page_cap),
            str(settings.parse_text_cap),
        ]
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=str(BACKEND_ROOT),
                timeout=settings.parse_timeout_seconds,
                capture_output=True,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HostileFile(
                "parse_timeout",
                "Parsing exceeded the time limit and was stopped.",
            ) from exc
        if not output.is_file():
            raise HostileFile("parser_crash", "The parser did not return a result.")
        payload = json.loads(output.read_text(encoding="utf-8"))
        if completed.returncode not in {0, None} and not payload.get("ok"):
            code = str(payload.get("error_code") or "parser_crash")
            message = str(payload.get("message") or "The parser failed.")
            raise HostileFile(code, message)
        if not payload.get("ok"):
            raise HostileFile(
                str(payload.get("error_code") or "parse_failed"),
                str(payload.get("message") or "The file could not be parsed."),
            )
        pages = [(int(item["page"]), str(item["text"])) for item in payload.get("pages", [])]
        warning = payload.get("warning")
        return ParseResult(pages=pages, warning=str(warning) if warning else None)
