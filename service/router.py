"""Route a question to the structured (DuckDB) or semantic (Chroma) store."""

from enum import Enum

# Keyword heuristic only — deliberately not tuned further until
# tests/test_router.py has real "weird guess" examples from the mentor
# to check accuracy against. Over-engineering this now would be tuning
# against guesses, not data.
STRUCTURED_KEYWORDS = ["rate", "%", "threshold", "how much"]


class Source(str, Enum):
    DUCKDB = "duckdb"
    CHROMA = "chroma"


def classify_query(question: str) -> Source:
    q = question.lower()
    if any(keyword in q for keyword in STRUCTURED_KEYWORDS):
        return Source.DUCKDB
    return Source.CHROMA
