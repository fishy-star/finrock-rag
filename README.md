# finrock-rag

Standalone RAG service grounding UK bookkeeping questions in GOV.UK
guidance and original notes. Separate service from Finrock's own
`internal/rag` — different runtime, different deploy cadence, and not
wired into any pipeline yet. See `finrock-rag-full-build-spec.md` for
the full design rationale.

**Retrieval is for prose, not for money.** This service returns a rule
passage + citation for an LLM to reason with — never a bare number
presented as fact. If a caller needs an exact figure (a VAT rate, a
threshold), that must come from a deterministic source, not this
service's similarity search.

## Setup

```bash
python3.12 -m venv .venv   # 3.12, not 3.14 — torch/sentence-transformers lag on new Python
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in ANTHROPIC_API_KEY if you want /rag/query
```

## Ingest content

```bash
# Scrape the GOV.UK seed pages into data/raw/*.txt
PYTHONPATH=. python ingest/scrape_govuk.py

# Chunk + embed everything in data/raw/ into the Chroma store
PYTHONPATH=. python -c "
from pathlib import Path
from ingest.chunker import chunk_document
from ingest.embed_and_store import store_chunks

for path in Path('data/raw').glob('*.txt'):
    text = path.read_text()
    chunks = chunk_document(text, source_url='', source_title=path.stem)
    print(path.name, store_chunks(chunks, source_type='govuk'), 'chunks stored')
"

# Seed the structured VAT rate table (DuckDB)
PYTHONPATH=. python ingest/load_structured.py
```

Or skip the CLI and use the upload form in the web UI once the server is
running — that's the intended path for the mentor's own notes and
uploaded documents.

## Run

```bash
uvicorn service.api:app --reload
```

Open http://127.0.0.1:8000 — upload a document, run "Check retrieval"
(free, no API key), and if `ANTHROPIC_API_KEY` is set, get a full
synthesized answer with citations.

## Test

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

`test_retrieval_accuracy.py` skips automatically if nothing has been
ingested yet.

## API

See `finrock-rag-full-build-spec.md` §5 for the full endpoint contract:
`POST /documents/upload`, `GET /documents`, `POST /rag/check` (free),
`POST /rag/query` (needs `ANTHROPIC_API_KEY`), `GET /healthz`.
