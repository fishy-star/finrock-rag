"""Split raw document text into retrievable chunks."""

from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    source_url: str
    source_title: str
    section_heading: str


def chunk_document(text: str, source_url: str, source_title: str) -> list[Chunk]:
    """Split on '\\n## ' markers — one chunk per section.

    Assumes the text was produced by scrape_govuk.py, which marks each
    heading as its own '## Heading' line. v1 does not merge very short
    sections or split very long ones — fine for GOV.UK's already
    well-structured pages, but a known simplification if this is reused
    for messier input.
    """
    if not text.strip():
        return []

    # Ensure the first section (before any "## ") is also captured.
    normalized = text if text.startswith("## ") else "## Introduction\n" + text

    raw_sections = normalized.split("\n## ")
    chunks = []
    for section in raw_sections:
        section = section.strip()
        if not section:
            continue
        if section.startswith("## "):
            section = section[3:]

        heading, _, body = section.partition("\n")
        body = body.strip()
        if not body:
            continue

        chunks.append(
            Chunk(
                text=body,
                source_url=source_url,
                source_title=source_title,
                section_heading=heading.strip(),
            )
        )
    return chunks


def chunk_note(text: str, note_title: str) -> list[Chunk]:
    """One chunk per paragraph, for pasted/uploaded text with no heading structure."""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [
        Chunk(
            text=paragraph,
            source_url="",
            source_title=note_title,
            section_heading=note_title,
        )
        for paragraph in paragraphs
    ]
