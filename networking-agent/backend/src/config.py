"""Settings loaded from the environment and `networking-agent/.env`."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(PROJECT_DIR / ".env")

LLM_MODEL = os.environ.get("LLM_MODEL", "anthropic:claude-haiku-5-5")
"""`<provider>:<model>` string understood by LangChain's `init_chat_model`."""

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(
    ","
)

AGENT_RECURSION_LIMIT = int(os.environ.get("AGENT_RECURSION_LIMIT", "40"))
"""Maximum LangGraph steps (each model call and each tool round counts)."""

LINKEDIN_MESSAGE_MAX_CHARS = max(1, int(os.environ.get("LINKEDIN_MESSAGE_MAX_CHARS", "300")))
"""Upper bound on each person's example LinkedIn connection note (LinkedIn allows 300)."""

DATABASE_DIR = Path(os.environ.get("DATABASE_DIR", PROJECT_DIR.parent / "database"))
"""Local JSON "database" for the POC (to be replaced by Supabase)."""

GOOGLE_RESOLVE_URLS = os.environ.get("GOOGLE_RESOLVE_URLS", "true").lower() != "false"
"""Follow Google's /goto redirects to real URLs (slower, but links are usable)."""

GOOGLE_CACHE_TTL_S = float(os.environ.get("GOOGLE_CACHE_TTL_S", "900"))
"""Seconds a Google results page is reused for a repeated query (0 turns the cache off)."""


LLM_USAGE_LOG = Path(os.environ.get("LLM_USAGE_LOG", BACKEND_DIR / "logs" / "llm_usage.csv"))
"""CSV with one row per LLM call (tokens, cost, user); see `llm_usage`."""


def provider_api_key(provider: str) -> str | None:
    """API key for `provider`, accepting this project's `<PROVIDER>_KEY` naming too."""
    name = provider.upper()
    return os.environ.get(f"{name}_API_KEY") or os.environ.get(f"{name}_KEY")
