"""Chunk + embed every scraped page in data/processed/ into Chroma.

Reads each `<slug>.json` sidecar (produced by scrape_bim.py /
scrape_govuk.py-style scrapers) alongside its `<slug>.txt` body, splits
the body into per-heading chunks (ingest/chunker.py), and stores them
via ingest/embed_and_store.py — which embeds title+body together, not
body alone, for every chunk it stores (see its store_chunks()); nothing
here special-cases old vs. new content, so that fix applies uniformly.

Resumable/idempotent like scrape_bim.py: which source slugs have
already been embedded is tracked in data/processed/.embed_state.json
(atomic writes, updated after every page), so re-running after an
interruption resumes instead of re-embedding — and therefore
duplicating in Chroma — pages already done. Files without a matching
.json sidecar (e.g. future hand-written internal_note uploads) are
left alone; this script only handles scraped-page pairs.
"""

import json
import sys
from pathlib import Path

from ingest.chunker import chunk_document
from ingest.embed_and_store import get_collection, store_chunks

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
STATE_PATH = OUT_DIR / ".embed_state.json"
SOURCE_TYPE = "govuk"


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"embedded": {}}  # slug -> chunk count


def _save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)  # atomic — a kill mid-write can't corrupt the real file


def run(force: bool = False) -> dict:
    state = _load_state()
    collection = get_collection()
    if force:
        state["embedded"] = {}

    processed = skipped = 0
    total_chunks = 0
    failed = []

    for json_path in sorted(OUT_DIR.glob("*.json")):
        slug = json_path.stem
        txt_path = json_path.with_suffix(".txt")
        if not txt_path.exists():
            continue

        if not force and slug in state["embedded"]:
            skipped += 1
            continue

        try:
            metadata = json.loads(json_path.read_text(encoding="utf-8"))
            text = txt_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"FAILED to read {slug}: {e}")
            failed.append(slug)
            continue

        title = metadata.get("title") or slug
        source_url = metadata.get("source_url", "")

        chunks = chunk_document(text, source_url=source_url, source_title=title)
        if not chunks:
            print(f"skip (no chunks): {slug}")
            state["embedded"][slug] = 0
            _save_state(state)
            continue

        if force and source_url:
            # drop this source's previously-stored chunks first so a
            # --force re-run replaces rather than duplicates them
            collection.delete(where={"source_url": source_url})

        try:
            count = store_chunks(chunks, source_type=SOURCE_TYPE)
        except Exception as e:
            print(f"FAILED to embed {slug}: {e}")
            failed.append(slug)
            continue

        state["embedded"][slug] = count
        total_chunks += count
        processed += 1
        _save_state(state)
        print(f"embedded: {slug} ({count} chunks) — {title!r}")

    return {
        "processed_this_run": processed,
        "skipped": skipped,
        "failed": failed,
        "total_chunks_this_run": total_chunks,
        "total_slugs_embedded": sum(1 for v in state["embedded"].values() if v or v == 0),
    }


if __name__ == "__main__":
    force_refresh = "--force" in sys.argv
    result = run(force=force_refresh)

    print(f"\n{'=' * 60}")
    print(f"Pages embedded this run:    {result['processed_this_run']}")
    print(f"Skipped (already done):    {result['skipped']}")
    print(f"Chunks added this run:      {result['total_chunks_this_run']}")
    print(f"Total pages embedded ever:  {result['total_slugs_embedded']}")
    print(f"Failed:                     {len(result['failed'])}")
    if result["failed"]:
        print("\nFailed slugs (re-run to retry):")
        for s in result["failed"]:
            print(f"  {s}")
    print(f"{'=' * 60}")
