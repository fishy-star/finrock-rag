"""Central config, loaded once from environment / .env at import time."""

import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./db/chroma_store")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "./db/reference.duckdb")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))

# Claude model used for synthesis. See claude-api skill / docs before
# changing — pin an exact model string, don't guess.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
