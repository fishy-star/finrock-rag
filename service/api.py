"""FastAPI app — the single entrypoint (`uvicorn service.api:app`)."""

import uuid
from collections import defaultdict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import ANTHROPIC_API_KEY
from ingest.chunker import chunk_document, chunk_note
from ingest.embed_and_store import get_collection, store_chunks
from ingest.parse_document import parse_upload
from ingest.load_structured import init_schema, load_vat_rates
from service.query_chroma import query_chroma
from service.query_duckdb import query_duckdb
from service.router import Source, classify_query
from service.synthesize import synthesize_answer

app = FastAPI(title="finrock-rag")

# Ensure the DuckDB starter table exists on boot — load_vat_rates() is
# idempotent (INSERT ... ON CONFLICT DO NOTHING), so this never wipes
# hand-edited rows on restart.
init_schema()
load_vat_rates()

OTHER_SOURCE_WARNING = (
    "Only ingest content you have rights to reproduce (GOV.UK/OGL content "
    "or your own original notes). Avoid uploading commercially copyrighted "
    "text verbatim."
)


class QuestionRequest(BaseModel):
    question: str


def _looks_like_headed_document(text: str) -> bool:
    return text.strip().startswith("## ") or "\n## " in text


def _duckdb_rows_to_chunks(rows: list[dict]) -> list[dict]:
    return [
        {
            "text": f"{r['scheme'].capitalize()} rate: {r['rate_pct']}% — {r['description']}",
            "metadata": {
                "source_title": "VAT rates (structured reference)",
                "source_url": "",
                "section_heading": r["scheme"],
            },
            "distance": 0.0,
        }
        for r in rows
    ]


@app.post("/documents/upload")
async def upload_document(
    title: str = Form(...),
    source_type: str = Form(...),
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
):
    if source_type not in ("govuk", "internal_note", "other"):
        raise HTTPException(400, "source_type must be one of: govuk, internal_note, other")

    if file is not None:
        content = await file.read()
        try:
            parsed_text = parse_upload(file.filename, content)
        except ValueError as e:
            raise HTTPException(400, str(e))
    elif text is not None and text.strip():
        parsed_text = text
    else:
        raise HTTPException(400, "Provide either a file or pasted text")

    if _looks_like_headed_document(parsed_text):
        chunks = chunk_document(parsed_text, source_url="", source_title=title)
    else:
        chunks = chunk_note(parsed_text, title)

    chunks_stored = store_chunks(chunks, source_type=source_type)

    response = {"chunks_stored": chunks_stored, "document_id": str(uuid.uuid4())}
    if source_type == "other":
        response["warning"] = OTHER_SOURCE_WARNING
    return response


@app.get("/documents")
def list_documents():
    collection = get_collection()
    if collection.count() == 0:
        return []

    data = collection.get(include=["metadatas"])
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for metadata in data["metadatas"]:
        key = (metadata.get("source_title", ""), metadata.get("source_type", ""))
        counts[key] += 1

    return [
        {"source_title": title, "source_type": source_type, "chunk_count": count}
        for (title, source_type), count in counts.items()
    ]


@app.post("/rag/check")
def rag_check(body: QuestionRequest):
    return {"chunks": query_chroma(body.question)}


@app.post("/rag/query")
def rag_query(body: QuestionRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            503, "ANTHROPIC_API_KEY is not configured — set it in .env to enable /rag/query"
        )

    source = classify_query(body.question)
    if source == Source.DUCKDB:
        context_chunks = _duckdb_rows_to_chunks(query_duckdb(body.question))
    else:
        context_chunks = query_chroma(body.question)

    return synthesize_answer(body.question, context_chunks)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "llm_configured": bool(ANTHROPIC_API_KEY)}


app.mount("/", StaticFiles(directory="service/static", html=True), name="static")
