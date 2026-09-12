"""Scrape the full HMRC Business Income Manual (BIM) into data/processed/
as text + JSON-sidecar metadata.

Standalone from scrape_govuk.py: BIM pages are HMRC's *internal manual*
template (a `.subsection-collection` contents list on index pages), not
the regular /guidance/ template scrape_govuk.py targets, and this feeds
data/processed/ (a staging area, no chunking/embedding here) rather than
data/raw/ (which scrape_govuk.py's chunk-ready output feeds).

Full-manual crawl (not hand-picked sections): starting from the manual's
top-level contents page, every page is fetched once and classified by
its own markup — a `.subsection-collection` container makes it an index
page (its links are queued for the same treatment); its absence makes it
a leaf page (scraped for content). This walks the whole tree — all ~13
top-level sections, at whatever depth each turns out to have — without
needing to know the manual's shape in advance.

At ~2,000-3,000+ leaf pages and a fixed per-request politeness delay,
a full run takes 1.5-2+ hours. To survive being interrupted (Ctrl-C,
terminal closed, machine sleep) and resumed later without re-fetching
anything already handled, crawl state — which URLs are known index
pages with which children, which leaf URLs are saved/empty/failed, and
the not-yet-visited frontier — is persisted to
data/processed/.bim_crawl_state.json after *every* page, via an atomic
write. Re-running `python ingest/scrape_bim.py` just picks the frontier
back up; already-saved leaf pages (checked against the actual .txt file
on disk, not just the state cache) are never re-fetched.
"""

import json
import re
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.gov.uk"
MANUAL_URL = f"{BASE_URL}/hmrc-internal-manuals/business-income-manual"
REQUEST_DELAY_SECONDS = 1.5

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
STATE_PATH = OUT_DIR / ".bim_crawl_state.json"

HEADING_TAGS = {"h1", "h2", "h3"}
CONTENT_TAGS = HEADING_TAGS | {"p", "li"}

LEAF_SLUG_RE = re.compile(r"^bim\d+$", re.I)


@dataclass
class Link:
    url: str
    text: str


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers={"User-Agent": "finrock-rag/0.1"}, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _clean_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("title")
    if title_tag is None:
        return ""
    # e.g. "BIM72005 - Cash basis: overview - HMRC internal manual - GOV.UK"
    return title_tag.get_text(strip=True).split(" - HMRC internal manual - GOV.UK")[0].strip()


def _clean_section_title(link_text: str) -> str:
    # e.g. "BIM40000Measuring the profits (...) - receipts & deductions: contents"
    text = re.sub(r"^BIM\d+", "", link_text, flags=re.I).strip()
    text = re.sub(r":\s*contents$", "", text, flags=re.I).strip()
    return text


def _extract_links(container) -> list[Link]:
    """Every bimNNNNN link in an index page's contents-list container,
    in document order, deduplicated. Non-numbered links (e.g. the
    BIMFEEDBACK form) are excluded — they aren't manual pages.
    """
    links = []
    seen = set()
    for a in container.select("a.section-link[href]"):
        href = a["href"]
        slug = _slug(href)
        if not LEAF_SLUG_RE.match(slug):
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append(Link(url=full_url, text=a.get_text(strip=True)))
    return links


def _table_to_markdown(table) -> str:
    """Render a <table> as a markdown table. BIM tables have no <th> —
    the first row is treated as the header, matching how these tables
    (e.g. mileage-rate tables) actually read.
    """
    rows = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _extract_content(soup: BeautifulSoup, url: str) -> tuple[str, str]:
    """Parse an already-fetched leaf page's soup into (title, text)."""
    title = _clean_title(soup)

    container = soup.select_one(".gem-c-govspeak")
    if container is None:
        raise RuntimeError(f"Expected '.gem-c-govspeak' content container not found on {url}")

    # GOV.UK renders BIM tables as <table><tr><td><p>...</p></td></tr></table>
    # with no <th>. The flat find_all(CONTENT_TAGS) walk below would
    # otherwise descend into those nested <p> tags right alongside real
    # paragraphs, losing all row/column structure (this is exactly what
    # flattened bim75005's mileage-rate tables into run-together text).
    # Pull tables out first and swap in a placeholder <p> so the walk
    # sees one line per table, in the correct position, instead of its
    # nested cells.
    table_markdown = {}
    for i, table in enumerate(container.find_all("table")):
        placeholder = f"__TABLE_PLACEHOLDER_{i}__"
        table_markdown[placeholder] = _table_to_markdown(table)
        placeholder_tag = soup.new_tag("p")
        placeholder_tag.string = placeholder
        table.replace_with(placeholder_tag)

    lines = []
    last_text = None
    for tag in container.find_all(list(CONTENT_TAGS)):
        text = tag.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue
        if text == last_text:
            continue
        last_text = text

        if text in table_markdown:
            lines.append(table_markdown[text])
        elif tag.name in HEADING_TAGS:
            lines.append(f"## {text}")
        elif tag.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)

    return title, "\n\n".join(lines)


def scrape_bim_page(url: str) -> tuple[str, str]:
    """Fetch one BIM leaf page, return (title, extracted_text)."""
    soup = _fetch(url)
    return _extract_content(soup, url)


def already_saved(slug: str) -> bool:
    return (OUT_DIR / f"{slug}.txt").exists()


def save_page(slug: str, title: str, text: str, url: str, section: str) -> None:
    (OUT_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
    metadata = {
        "title": title,
        "source_url": url,
        "section": section,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    (OUT_DIR / f"{slug}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "url_root": {},  # leaf/index url -> top-level section slug it descends from
        "root_titles": {},  # top-level section slug -> human title
        "index_children_known": {},  # index url -> [child urls], once expanded
        "leaf_status": {},  # leaf url -> "saved" | "empty" | "failed"
        "frontier": [],  # not-yet-visited urls, in queue order
    }


def _save_state(state: dict, frontier: "deque[str]") -> None:
    state["frontier"] = list(frontier)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)  # atomic — a kill mid-write can't corrupt the real file


def crawl(force: bool = False) -> dict:
    """Walk the full BIM tree from MANUAL_URL, scraping every leaf page.

    Resumable: state (and every saved page) is written to disk as it's
    produced, so re-running after an interruption continues rather than
    restarting. `force` re-scrapes leaf pages already saved on disk;
    it does not affect index-page traversal, which is always resumed
    from cached children (the manual's shape doesn't change mid-run).
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    frontier: deque = deque(state["frontier"]) if state["frontier"] else deque([MANUAL_URL])

    # "failed"/"empty" leaves were popped off the frontier for good on the
    # run that hit them — without re-queuing, a transient error (timeout,
    # 500) would be permanent. Retrying is cheap and idempotent, so redo
    # them on every resume rather than requiring a manual re-run.
    in_frontier = set(frontier)
    for url, status in state["leaf_status"].items():
        if status in ("failed", "empty") and url not in in_frontier:
            frontier.append(url)
            in_frontier.add(url)

    saved_this_run = 0
    while frontier:
        url = frontier.popleft()

        if url in state["index_children_known"]:
            continue  # index page already expanded in a previous run

        slug = _slug(url)
        if not force and already_saved(slug):
            state["leaf_status"][url] = "saved"
            print(f"skip (already saved): {slug}")
            _save_state(state, frontier)
            continue

        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            soup = _fetch(url)
        except Exception as e:
            print(f"FAILED to fetch {url}: {e}")
            state["leaf_status"][url] = "failed"
            _save_state(state, frontier)
            continue

        container = soup.select_one(".subsection-collection")
        if container is not None:
            links = _extract_links(container)
            is_top = url == MANUAL_URL
            for link in links:
                if is_top:
                    root_slug = _slug(link.url)
                    state["root_titles"][root_slug] = _clean_section_title(link.text)
                    state["url_root"][link.url] = root_slug
                elif link.url not in state["url_root"]:
                    state["url_root"][link.url] = state["url_root"].get(url, "unknown")
                already_known = (
                    link.url in state["index_children_known"] or state["leaf_status"].get(link.url) == "saved"
                )
                if not already_known:
                    frontier.append(link.url)
            state["index_children_known"][url] = [link.url for link in links]
            print(f"[index] {url} -> {len(links)} links")
        else:
            section = state["url_root"].get(url, "unknown")
            try:
                title, text = _extract_content(soup, url)
            except Exception as e:
                print(f"FAILED to parse {url}: {e}")
                state["leaf_status"][url] = "failed"
                _save_state(state, frontier)
                continue

            if not text.strip():
                print(f"FAILED (empty content) for {url}")
                state["leaf_status"][url] = "empty"
            else:
                save_page(slug, title, text, url, section)
                state["leaf_status"][url] = "saved"
                saved_this_run += 1
                print(f"saved [{section}]: {slug} ({len(text)} chars) — {title!r}")

        _save_state(state, frontier)

    return {
        "saved_this_run": saved_this_run,
        "total_saved": sum(1 for v in state["leaf_status"].values() if v == "saved"),
        "failed": [u for u, v in state["leaf_status"].items() if v == "failed"],
        "empty": [u for u, v in state["leaf_status"].items() if v == "empty"],
    }


if __name__ == "__main__":
    force_refresh = "--force" in sys.argv
    result = crawl(force=force_refresh)

    print(f"\n{'=' * 60}")
    print(f"Pages saved this run:  {result['saved_this_run']}")
    print(f"Total pages saved:     {result['total_saved']}")
    print(f"Failed:                {len(result['failed'])}")
    print(f"Empty:                 {len(result['empty'])}")
    if result["failed"]:
        print("\nFailed URLs (re-run to retry):")
        for u in result["failed"]:
            print(f"  {u}")
    print(f"{'=' * 60}")
