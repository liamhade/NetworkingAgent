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

MAX_COMPANIES = max(1, int(os.environ.get("MAX_COMPANIES", "6")))
"""Most companies a search returns, ranked by fit (score 0-100)."""

PEOPLE_AUTO_COMPANIES = max(0, int(os.environ.get("PEOPLE_AUTO_COMPANIES", "3")))
"""The top-ranked companies that get a people search during the search; the rest get one
on demand ("Find People To Connect With")."""

PEOPLE_PER_COMPANY = max(1, int(os.environ.get("PEOPLE_PER_COMPANY", "3")))
"""The people-search ladder stops once this many current employees were found."""

PEOPLE_SEARCH_N = max(1, min(10, int(os.environ.get("PEOPLE_SEARCH_N", "5"))))
"""Profiles asked for per people search (more is slower: each link is resolved)."""

READ_POSTINGS = max(0, int(os.environ.get("READ_POSTINGS", "2")))
"""Job postings read in full for requirements and salary (0 turns it off)."""

READ_POSTING_MAX_CHARS = max(1_000, int(os.environ.get("READ_POSTING_MAX_CHARS", "4000")))
"""Characters of each read posting passed to the compile step."""

ATS_MAX_BOARDS = max(0, int(os.environ.get("ATS_MAX_BOARDS", "6")))
"""Most ATS boards (Greenhouse, Lever or Ashby boards) fetched per search (0 turns ATS off)."""

ATS_JOBS_PER_BOARD = max(1, int(os.environ.get("ATS_JOBS_PER_BOARD", "4")))
"""Matching postings kept from each ATS board."""

ATS_RESOLVE_LINKS = max(0, int(os.environ.get("ATS_RESOLVE_LINKS", "3")))
"""Google links resolved per ATS board search when the breadcrumb doesn't show the board."""

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
