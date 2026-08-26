"""Extract plain text from documents the mentor uploads directly (not scraped)."""

import io
from pathlib import Path

from pypdf import PdfReader


def parse_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def parse_pdf(path: str) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def parse_upload(filename: str, content: bytes) -> str:
    """Dispatch by file extension. Raises ValueError for unsupported types."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        return content.decode("utf-8")
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)

    raise ValueError(f"Unsupported file type: {suffix!r} (expected .txt or .pdf)")
