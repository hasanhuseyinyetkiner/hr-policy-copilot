#!/usr/bin/env python3
"""Fail if markdown files contain broken relative local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        rel = path.relative_to(ROOT).as_posix()
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts[:-1]):
            continue
        if "/node_modules/" in f"/{rel}/" or "/dist/" in f"/{rel}/":
            continue
        files.append(path)
    return sorted(files)


def resolve_target(source: Path, raw: str) -> Path | None:
    target = raw.strip()
    if not target or target.startswith(SKIP_PREFIXES) or target.startswith("#"):
        return None
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    path_part = target.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None
    return (source.parent / path_part).resolve()


def main() -> int:
    broken: list[str] = []
    checked = 0
    for md in iter_markdown_files():
        text = md.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            resolved = resolve_target(md, match.group(2))
            if resolved is None:
                continue
            checked += 1
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                # Allow links that escape the repo only if the path exists;
                # still report missing targets.
                pass
            if not resolved.exists():
                rel_md = md.relative_to(ROOT).as_posix()
                broken.append(f"{rel_md}: [{match.group(1)}]({match.group(2)})")

    if broken:
        print(f"Broken local markdown links ({len(broken)}):", file=sys.stderr)
        for item in broken:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(f"OK: checked {checked} local links across {len(list(iter_markdown_files()))} markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
