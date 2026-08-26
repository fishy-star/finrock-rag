"""Semantic retrieval over the Chroma vector store."""

from config import RETRIEVAL_TOP_K
from ingest.embed_and_store import embed_texts, get_collection


def query_chroma(question: str, top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
    """Embed the question with the same model used at ingest time and
    return the top_k nearest chunks as [{text, metadata, distance}, ...].
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_texts([question])[0]
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
    )

    hits = []
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    for text, metadata, distance in zip(documents, metadatas, distances):
        hits.append({"text": text, "metadata": metadata, "distance": distance})
    return hits
