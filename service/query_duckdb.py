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
    """If the question names a specific scheme (standard/reduced/zero),
    return just that row via query_vat_rate(). Otherwise return all rows.

    TODO: real keyword/NL matching once there's more than one table —
    this substring check is only viable because vat_rates.scheme has
    exactly three known literal values.
    """
    q = question.lower()
    for scheme in ("standard", "reduced", "zero"):
        if scheme in q:
            row = query_vat_rate(scheme)
            return [row] if row else []

    conn = get_connection()
    rows = conn.execute("SELECT scheme, rate_pct, description FROM vat_rates").fetchall()
    conn.close()
    return [{"scheme": r[0], "rate_pct": r[1], "description": r[2]} for r in rows]
