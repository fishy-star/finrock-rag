# data/processed/

## What's actually here right now

The 52 `.txt`/`.json` file pairs in this folder are the output of
`ingest/scrape_bim.py` — HMRC's Business Income Manual, cash basis
(`bim72xxx`) and simplified expenses (`bim75xxx`) sections, one page per
pair:

- `<slug>.txt` — the extracted guidance text (e.g. `bim72005.txt`).
  Tables are rendered as markdown tables, not flattened prose.
- `<slug>.json` — metadata sidecar: `title`, `source_url`, `section`
  (`cash_basis` | `simplified_expenses`), `scraped_at`.

This is real GOV.UK/HMRC content (Crown copyright, Open Government
Licence) — safe to store verbatim under the content policy in
`finrock-rag-full-build-spec.md` §0, unlike the reference ebook.

Regenerate/extend with:

```bash
PYTHONPATH=. python ingest/scrape_bim.py           # skips pages already saved
PYTHONPATH=. python ingest/scrape_bim.py --force   # re-fetches everything
```

**Nothing in the codebase reads this folder automatically yet.** These
files are staged text, not ingested into Chroma — chunking + embedding
them (via `ingest/chunker.py` / `ingest/embed_and_store.py`, or the
`/documents/upload` endpoint) is a follow-up step, not yet built.

## Secondary, not-yet-used purpose

This folder is also the intended staging spot for original notes
written *from* the reference ebook — never the ebook's text itself
(commercial copyright, not a style preference; see spec §0). Workflow,
once you're working from the ebook:

1. Read a chapter/section of the ebook.
2. Extract the *concept*, and write a short note in your own words —
   save it here as a `.txt` file.
3. Paste that note's contents into the "Upload a document" form in the
   web UI (or `POST /documents/upload`), tagged `source_type: internal_note`.

No ebook-derived notes exist here yet — only the BIM scrape output
above. If both kinds of file end up living here at once, the `.json`
sidecar (present only for scraped pages) is how to tell them apart.
