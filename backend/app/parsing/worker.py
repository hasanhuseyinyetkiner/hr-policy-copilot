"""Subprocess entry point for untrusted document parsing.

Run as ``python -m app.parsing.worker <input> <output> <extension> <page_cap> <text_cap>``.
The parent process enforces the timeout. This module must not import the
embedding stack.
"""

import json
import sys
from pathlib import Path

from app.parsing.extract import ExtractError, extract_document


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 5:
        print("usage: worker input output extension page_cap text_cap", file=sys.stderr)
        return 2
    input_path, output_path, extension, page_cap, text_cap = args
    payload: dict[str, object]
    try:
        pages, warning = extract_document(
            Path(input_path),
            extension,
            page_cap=int(page_cap),
            text_cap=int(text_cap),
        )
        if not any(text.strip() for _page, text in pages):
            payload = {
                "ok": False,
                "error_code": "empty_document",
                "message": "No text could be extracted.",
                "pages": [],
                "warning": None,
            }
        else:
            payload = {
                "ok": True,
                "error_code": None,
                "message": None,
                "pages": [{"page": page, "text": text} for page, text in pages],
                "warning": warning,
            }
    except ExtractError as exc:
        payload = {
            "ok": False,
            "error_code": exc.code,
            "message": exc.message,
            "pages": [],
            "warning": None,
        }
    except Exception:
        payload = {
            "ok": False,
            "error_code": "parser_crash",
            "message": "The parser stopped unexpectedly.",
            "pages": [],
            "warning": None,
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
