"""Structured reference data (DuckDB) — for exact lookups, not semantic search.

v1 starter set only. Expanding this table depends on real examples from
the mentor about which structured lookups actually matter — not
guesswork now.
"""

import duckdb

from config import DUCKDB_PATH


def get_connection():
    return duckdb.connect(DUCKDB_PATH)


def init_schema():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vat_rates (
            scheme VARCHAR PRIMARY KEY,
            rate_pct DOUBLE,
            description VARCHAR
        )
        """
    )
    conn.close()


def load_vat_rates():
    conn = get_connection()
    conn.execute("DELETE FROM vat_rates")
    conn.executemany(
        "INSERT INTO vat_rates VALUES (?, ?, ?)",
        [
            ("standard", 20.0, "Most goods and services"),
            ("reduced", 5.0, "Some goods and services, e.g. children's car seats, home energy"),
            ("zero", 0.0, "Zero-rated goods and services, e.g. most food, children's clothes"),
        ],
    )
    conn.close()


if __name__ == "__main__":
    init_schema()
    load_vat_rates()
    conn = get_connection()
    print(conn.execute("SELECT * FROM vat_rates").fetchall())
    conn.close()
