"""Narrow contradiction heuristic for the seeded office-day policies.

This is not a general entailment model. It only flags current passages that
state different integer ``in-office days`` requirements.
"""

import re

_OFFICE_DAYS = re.compile(r"(\d+)\s+in-office\s+days?\b", re.IGNORECASE)


def office_day_claims(text: str) -> set[int]:
    return {int(match.group(1)) for match in _OFFICE_DAYS.finditer(text)}


def conflicting_office_days(texts: list[str]) -> set[int]:
    found: set[int] = set()
    for text in texts:
        found |= office_day_claims(text)
    return found
