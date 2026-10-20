"""Shared tokenizer for indexing and queries."""

import re

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "to",
        "for",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "that",
        "this",
        "it",
        "its",
        "if",
        "not",
        "no",
        "do",
        "does",
        "how",
        "what",
        "when",
        "where",
        "who",
        "which",
        "many",
        "much",
        "per",
        "our",
        "their",
        "they",
        "we",
        "you",
        "your",
        "each",
        "must",
        "can",
        "about",
        "into",
        "than",
        "then",
        "also",
        "any",
        "all",
    }
)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        if len(raw) < 2 and not raw.isdigit():
            continue
        tokens.append(raw)
    return tokens


def unique_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokenize(text):
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered
