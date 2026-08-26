"""LLM synthesis over retrieved chunks — answers only from provided context."""

import anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

SYSTEM_PROMPT = """You are a UK bookkeeping reference assistant. Answer the \
question using ONLY the context passages provided below — never use outside \
knowledge, and never fill gaps with a guess.

If the context does not clearly answer the question, respond with exactly:
NOT_COVERED

Do not state or imply an exact figure (a rate, a threshold, a date) unless \
it is stated verbatim in the context. When you do answer, keep it grounded \
in what the passages actually say."""


def synthesize_answer(question: str, context_chunks: list[dict]) -> dict:
    """Call Claude to answer `question` from `context_chunks` only.

    context_chunks: [{text, metadata, distance}, ...] as returned by
    query_chroma()/query_duckdb(). Raises RuntimeError if
    ANTHROPIC_API_KEY isn't set — the API layer is responsible for
    making synthesis optional, not this function.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set — synthesize_answer() requires it.")

    if not context_chunks:
        return {"answer": "NOT_COVERED", "sources": [], "confidence": "no_match"}

    context_text = "\n\n---\n\n".join(
        f"[Source: {c['metadata'].get('source_title', 'unknown')} — "
        f"{c['metadata'].get('section_heading', '')}]\n{c['text']}"
        for c in context_chunks
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low"},
        messages=[
            {"role": "user", "content": f"Context:\n\n{context_text}\n\nQuestion: {question}"}
        ],
    )

    answer = next((b.text for b in response.content if b.type == "text"), "").strip()

    if answer == "NOT_COVERED":
        return {"answer": answer, "sources": [], "confidence": "no_match"}

    sources = [
        {
            "source_title": c["metadata"].get("source_title", ""),
            "source_url": c["metadata"].get("source_url", ""),
            "section_heading": c["metadata"].get("section_heading", ""),
        }
        for c in context_chunks
    ]
    return {"answer": answer, "sources": sources, "confidence": "grounded"}
