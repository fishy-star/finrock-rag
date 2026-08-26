"""Round-trip a small sample .txt and .pdf through parse_document.py."""

from pathlib import Path

import pytest

from ingest.parse_document import parse_pdf, parse_txt, parse_upload

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_txt_returns_nonempty_text():
    text = parse_txt(str(FIXTURES / "sample.txt"))
    assert text.strip()
    assert "Sample section" in text


def test_parse_pdf_returns_nonempty_text():
    text = parse_pdf(str(FIXTURES / "sample.pdf"))
    assert text.strip()
    assert "Hello PDF" in text


def test_parse_upload_dispatches_by_extension():
    txt_bytes = (FIXTURES / "sample.txt").read_bytes()
    assert "Sample section" in parse_upload("note.txt", txt_bytes)

    pdf_bytes = (FIXTURES / "sample.pdf").read_bytes()
    assert "Hello PDF" in parse_upload("scan.pdf", pdf_bytes)


def test_parse_upload_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        parse_upload("document.docx", b"irrelevant")
