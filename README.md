# finrock-rag

A retrieval-augmented generation (RAG) system for searching HMRC's
**Business Income Manual** (BIM) and related GOV.UK guidance (VAT
rates, VAT registration, record-keeping). Ask a plain-English
bookkeeping question and get back an answer grounded only in the
ingested guidance — with sources — or an explicit refusal if the
guidance doesn't cover it.

## What it does

- Scrapes official GOV.UK / HMRC internal-manual content (Crown
  copyright, Open Government Licence — safe to store verbatim).
- Splits it into per-section chunks and embeds them locally.
- At query time, retrieves the most relevant chunks (semantic search
  over the manual + exact lookups from a small structured reference
  table) and hands them to an LLM that is instructed to answer **only**
  from that context — never from its own general knowledge — and to
  say so explicitly when the context doesn't cover the question.

## Pipeline

```
scrape  →  chunk / embed  →  retrieve  →  generate
```

| Stage | What happens | Code |
| --- | --- | --- |
| **Scrape** | Fetch GOV.UK/HMRC pages, extract clean text (tables rendered as markdown, headings marked `## Heading`) | [`ingest/scrape_bim.py`](ingest/scrape_bim.py) (full Business Income Manual, resumable crawl), [`ingest/scrape_govuk.py`](ingest/scrape_govuk.py) (VAT guidance pages) |
| **Chunk / embed** | Split scraped text on `## ` headings into one chunk per section, embed **title + body** together (not body alone — the title often carries the strongest topical signal), store in Chroma | [`ingest/chunker.py`](ingest/chunker.py), [`ingest/embed_and_store.py`](ingest/embed_and_store.py), driven by [`ingest/load_processed_to_chroma.py`](ingest/load_processed_to_chroma.py) |
| **Retrieve** | Embed the question with the same model, do nearest-neighbour search over Chroma; merge with any exact-match rows from the DuckDB reference table (no upfront classifier — both are always queried and merged) | [`service/query_chroma.py`](service/query_chroma.py), [`service/query_duckdb.py`](service/query_duckdb.py) |
| **Generate** | Send the question + retrieved context to an LLM with a strict "answer only from context, or say NOT_COVERED" system prompt | [`service/synthesize.py`](service/synthesize.py) |

All of it is served over HTTP by [`service/api.py`](service/api.py)
(`uvicorn service.api:app`).

## Stack

- **ChromaDB** — local persistent vector store (`db/chroma_store/`), cosine similarity
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local, free, no API key, embeds both documents and queries
- **DuckDB** — small structured reference table (`db/reference.duckdb`) for exact lookups (e.g. VAT rates) alongside semantic search
- **Groq** (`openai/gpt-oss-120b`, OpenAI-compatible chat completions) — free-tier LLM used only for the final synthesis step; nothing else in the pipeline needs an API key
- **FastAPI** — HTTP API (`service/api.py`), plus a minimal static UI at `service/static/`

## Setup

```bash
# 1. Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and set GROQ_API_KEY (required only for /rag/query — see below)
```

`.env` options (all optional except `GROQ_API_KEY`, with defaults shown):

```
GROQ_API_KEY=            # required only for POST /rag/query
CHROMA_DIR=./db/chroma_store
DUCKDB_PATH=./db/reference.duckdb
RETRIEVAL_TOP_K=5
```

### Populate the data

```bash
# Scrape the full Business Income Manual (resumable — safe to Ctrl-C and re-run)
PYTHONPATH=. python ingest/scrape_bim.py

# Scrape the seed VAT guidance pages
python ingest/scrape_govuk.py

# Chunk + embed everything in data/processed/ into Chroma (also resumable/idempotent)
PYTHONPATH=. python ingest/load_processed_to_chroma.py

# Create the DuckDB reference table (VAT rates)
python ingest/load_structured.py
```

### Run the API

```bash
uvicorn service.api:app --reload
```

Then open `http://127.0.0.1:8000/` for the static UI, or hit the API directly (see below).

## Testing

### 1. Unit / accuracy tests (pytest)

```bash
pytest
```

Runs parser round-trip tests and a retrieval-accuracy check (real
questions against the ingested Chroma collection — auto-skips if the
collection is empty, e.g. on a fresh checkout before ingestion).

### 2. Retrieval-only testing — `POST /rag/check`

No LLM, no API key required. Returns the raw top-k chunks Chroma
retrieves for a question, so you can sanity-check retrieval quality in
isolation from generation:

```bash
curl -s -X POST http://127.0.0.1:8000/rag/check \
  -H "Content-Type: application/json" \
  -d '{"question": "am I eligible for the cash basis"}' | python3 -m json.tool
```

### 3. Full end-to-end testing — `POST /rag/query`

Requires `GROQ_API_KEY` set. Returns a synthesized answer, its
sources, and a confidence label (`grounded` or `no_match`).

**Example — grounded, in-corpus question:**

```bash
curl -s -X POST http://127.0.0.1:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "what mileage rate can I claim for a car on the cash basis"}' | python3 -m json.tool
```

```json
{
  "answer": "...55p per mile for the first 10,000 business miles, 25p after...",
  "sources": [
    {"source_title": "BIM75005 - Simplified expenses: expenditure on motor vehicles", "source_url": "https://www.gov.uk/hmrc-internal-manuals/business-income-manual/bim75005", "section_heading": "..."}
  ],
  "confidence": "grounded"
}
```

**Example — personally-phrased eligibility question:**

```bash
curl -s -X POST http://127.0.0.1:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "am I eligible for the cash basis"}' | python3 -m json.tool
```

Should return `"confidence": "grounded"` with the actual eligibility
criteria explained (receipt threshold, exclusions, etc.) — the system
prompt is specifically tuned to explain conditions from context for
"am I eligible / can I / should I"-style questions rather than
refusing just because it can't confirm your personal situation.

### 4. Regression check — out-of-scope questions should refuse

Ask something the ingested corpus has no bearing on and confirm it
still refuses rather than guessing from the model's general knowledge:

```bash
curl -s -X POST http://127.0.0.1:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "am I eligible for a state pension at 60"}' | python3 -m json.tool
```

Expected:

```json
{"answer": "NOT_COVERED", "sources": [], "confidence": "no_match"}
```

Run this alongside the eligibility example above whenever the system
prompt changes — it's the check that the "explain conditions instead
of refusing" fix didn't loosen refusal for genuinely out-of-scope
questions.
