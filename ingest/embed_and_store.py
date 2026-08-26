"""Embed chunks with a local sentence-transformers model and store in Chroma."""

from datetime import datetime, timezone

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMA_DIR
from ingest.chunker import Chunk

COLLECTION_NAME = "govuk_bookkeeping"

# Loaded once at import time (not per call) — downloads weights on first
# run, cached under ~/.cache after that. Free, local, no API key.
_model = SentenceTransformer("all-MiniLM-L6-v2")

_client = None


def get_collection():
    """Return the persistent Chroma collection, creating it if needed.

    embedding_function=None because embeddings are always computed
    ourselves via embed_texts() and passed explicitly — we don't rely on
    Chroma's own (different, less controllable) embedding function.
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    # all-MiniLM-L6-v2 is trained for cosine similarity, not raw L2
    # distance (Chroma's default) — without this, nearest-neighbour
    # ranking is noticeably worse.
    return _client.get_or_create_collection(
        COLLECTION_NAME,
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    # normalize_embeddings=True pairs with hnsw:space="cosine" above —
    # both sides need to agree on the same similarity convention.
    return _model.encode(texts, normalize_embeddings=True).tolist()


def store_chunks(chunks: list[Chunk], source_type: str) -> int:
    """Embed chunks and write them to Chroma. Returns count stored.

    source_type is one of "govuk" | "internal_note" | "other".
    """
    if not chunks:
        return 0

    collection = get_collection()
    embeddings = embed_texts([c.text for c in chunks])
    ingested_at = datetime.now(timezone.utc).isoformat()

    # Chroma ids must be unique strings; base them on current collection
    # size plus index so repeated calls in the same process don't collide.
    start = collection.count()
    ids = [f"chunk-{start + i}" for i in range(len(chunks))]

    metadatas = [
        {
            "source_url": c.source_url,
            "source_title": c.source_title,
            "section_heading": c.section_heading,
            "source_type": source_type,
            "ingested_at": ingested_at,
        }
        for c in chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=metadatas,
    )
    return len(chunks)
