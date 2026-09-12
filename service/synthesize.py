"""LLM synthesis over retrieved chunks — answers only from provided context.

Uses Groq's free-tier API (OpenAI-compatible chat completions) rather
than a paid provider. Implemented via plain `requests` — Groq's API is
a single simple endpoint, and `requests` is already a dependency, so
this avoids adding a new SDK for one function.
"""

import requests

from config import GROQ_API_KEY, GROQ_MODEL

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are a UK bookkeeping reference assistant. Answer the \
question using ONLY the context passages provided below — never use outside \
knowledge, and never fill gaps with a guess.

If the context does not clearly answer the question, respond with exactly:
NOT_COVERED

If the question is phrased personally ("am I eligible", "can I claim X", \
"should I do Y") and the context contains the general criteria or \
conditions for that topic, explain those conditions directly (e.g. "You're \
eligible if X, Y, Z — you're excluded if...") even though the context can't \
know the user's own circumstances. Only respond NOT_COVERED when the \
context genuinely lacks information relevant to the question — not merely \
because it can't confirm the user's personal situation.

Do not state or imply an exact figure (a rate, a threshold, a date) unless \
it is stated verbatim in the context. When you do answer, keep it grounded \
in what the passages actually say."""


def synthesize_answer(question: str, context_chunks: list[dict]) -> dict:
    """Call Groq to answer `question` from `context_chunks` only.

    context_chunks: [{text, metadata, distance}, ...] as returned by
    query_chroma()/query_duckdb(). Raises RuntimeError if GROQ_API_KEY
    isn't set — the API layer is responsible for making synthesis
    optional, not this function.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set — synthesize_answer() requires it.")

    if not context_chunks:
        return {"answer": "NOT_COVERED", "sources": [], "confidence": "no_match"}

    context_text = "\n\n---\n\n".join(
        f"[Source: {c['metadata'].get('source_title', 'unknown')} — "
        f"{c['metadata'].get('section_heading', '')}]\n{c['text']}"
        for c in context_chunks
    )

    response = requests.post(
        GROQ_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n\n{context_text}\n\nQuestion: {question}",
                },
            ],
        },
        timeout=30,
    )
    response.raise_for_status()

    answer = response.json()["choices"][0]["message"]["content"].strip()

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
