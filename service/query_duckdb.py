"""Exact structured lookups over DuckDB reference tables."""

from ingest.load_structured import get_connection


def query_vat_rate(scheme: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT scheme, rate_pct, description FROM vat_rates WHERE scheme = ?",
        [scheme],
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"scheme": row[0], "rate_pct": row[1], "description": row[2]}


def query_duckdb(question: str) -> list[dict]:
    """v1: return all vat_rates rows regardless of question text.

    TODO: real keyword/NL matching once there's more than one table —
    not worth building against a single table with three rows.
    """
    conn = get_connection()
    rows = conn.execute("SELECT scheme, rate_pct, description FROM vat_rates").fetchall()
    conn.close()
    return [{"scheme": r[0], "rate_pct": r[1], "description": r[2]} for r in rows]
