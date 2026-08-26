"""Scrape GOV.UK guidance pages into the '## Heading' text format chunker.py expects."""

import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# TODO: expand once real "weird guess" categorization examples come in
# from the mentor — these three are a starting point, not a survey.
SEED_URLS = [
    "https://www.gov.uk/vat-rates",
    "https://www.gov.uk/vat-registration",
    "https://www.gov.uk/keeping-your-pay-tax-records",
]

HEADING_TAGS = {"h1", "h2", "h3"}
CONTENT_TAGS = HEADING_TAGS | {"p", "li"}


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str


def _slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def scrape_page(url: str) -> ScrapedPage:
    response = requests.get(url, headers={"User-Agent": "finrock-rag/0.1"}, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # .gem-c-govspeak is GOV.UK's actual guidance-body container — it
    # excludes the contents nav, breadcrumbs, and the "Related
    # content"/"Explore the topic" sidebar that #content/main both pull
    # in. Fall back to the looser selectors for pages that don't use it.
    container = (
        soup.select_one(".gem-c-govspeak")
        or soup.select_one("#content")
        or soup.find("main")
        or soup
    )

    lines = []
    last_text = None
    for tag in container.find_all(list(CONTENT_TAGS)):
        text = tag.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        # GOV.UK markup sometimes nests a duplicate node (e.g. a <p>
        # mirroring its parent <li>'s text) — skip back-to-back repeats
        # of the same underlying text regardless of tag type.
        if text == last_text:
            continue
        last_text = text

        if tag.name in HEADING_TAGS:
            lines.append(f"## {text}")
        elif tag.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    return ScrapedPage(url=url, title=title, text="\n\n".join(lines))


def scrape_all(urls: list[str]) -> list[ScrapedPage]:
    return [scrape_page(url) for url in urls]


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    for page in scrape_all(SEED_URLS):
        path = out_dir / f"{_slug(page.url)}.txt"
        path.write_text(page.text, encoding="utf-8")
        print(f"wrote {path} ({len(page.text)} chars) — {page.title!r}")
