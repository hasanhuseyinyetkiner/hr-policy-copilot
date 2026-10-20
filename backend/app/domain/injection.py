"""Detect uploaded text that tries to override the assistant.

Extractive mode never executes document text. Chunks that look like
instruction overrides are also dropped from evidence.
"""

import re

_PATTERNS = (
    re.compile(r"ignore\s+(all|any|previous|prior)\s+(instructions|rules|policies)", re.I),
    re.compile(r"disregard\s+(the\s+)?(policy|policies|instructions)", re.I),
    re.compile(r"you\s+are\s+now\b", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"do\s+not\s+follow\s+(the\s+)?(policy|rules|instructions)", re.I),
)


def is_instruction_override(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PATTERNS)
