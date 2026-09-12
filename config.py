"""Central config, loaded once from environment / .env at import time."""

import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./db/chroma_store")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./db/reference.duckdb")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))

# Free-tier Groq model used for synthesis. llama-3.3-70b-versatile
# (from console.groq.com/docs/models) turned out to be retired/
# inaccessible — verified against a live GET /v1/models call with a
# real key instead of trusting docs alone. gpt-oss-120b confirmed
# active there.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
