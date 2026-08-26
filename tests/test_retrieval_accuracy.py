"""Question -> expected section heading, run against the ingested GOV.UK VAT page.

Skips if the Chroma collection is empty (fresh checkout, nothing ingested
yet) rather than failing — this is an accuracy check on real ingested
data, not a fixture test.
"""

import pytest

from ingest.embed_and_store import get_collection
from service.query_chroma import query_chroma

EVAL_CASES = [
    ("What happens if I register for VAT late?", "Late registration"),
    (
        "What happens if I take over a VAT-registered business?",
        "If you take over a VAT -registered business",
    ),
    (
        "What if I only sell VAT exempt goods in Northern Ireland?",
        "If you’re based in Northern Ireland and sell goods or services that are VAT exempt",
    ),
]


@pytest.fixture(autouse=True)
def skip_if_empty():
    if get_collection().count() == 0:
        pytest.skip("Chroma collection is empty — run the ingestion steps first")


@pytest.mark.parametrize("question,expected_heading", EVAL_CASES)
def test_top_hit_matches_expected_section(question, expected_heading):
    hits = query_chroma(question, top_k=1)
    assert hits, f"no hits returned for {question!r}"
    assert hits[0]["metadata"]["section_heading"] == expected_heading
