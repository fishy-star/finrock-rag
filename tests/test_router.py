"""Known question -> expected Source cases.

Extend with real "weird guess" examples once the mentor provides them —
see the comment in service/router.py.
"""

from service.router import Source, classify_query


def test_rate_question_routes_to_duckdb():
    assert classify_query("What is the VAT rate on children's clothes?") == Source.DUCKDB


def test_threshold_question_routes_to_duckdb():
    assert classify_query("What is the VAT registration threshold?") == Source.DUCKDB


def test_percent_symbol_routes_to_duckdb():
    assert classify_query("Is home energy taxed at 5%?") == Source.DUCKDB


def test_how_much_question_routes_to_duckdb():
    assert classify_query("How much VAT do I owe on this sale?") == Source.DUCKDB


def test_prose_question_routes_to_chroma():
    assert classify_query("How do I register for VAT?") == Source.CHROMA


def test_recordkeeping_question_routes_to_chroma():
    assert classify_query("How long do I need to keep my tax records?") == Source.CHROMA
