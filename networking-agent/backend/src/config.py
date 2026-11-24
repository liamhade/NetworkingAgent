"""Settings loaded from the environment and `networking-agent/.env`."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(PROJECT_DIR / ".env")


def _unquote_environment() -> None:
    """Strip one pair of matching quotes around any environment value.

    python-dotenv unquotes `KEY="value"`, but `docker run --env-file` and hosting dashboards
    keep the quotes, which turns a valid API key into an invalid one.
    """
    for name, value in list(os.environ.items()):
        stripped = value.strip()
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
            os.environ[name] = stripped[1:-1]


_unquote_environment()

LLM_MODEL = os.environ.get("LLM_MODEL", "anthropic:claude-haiku-5-5")
"""`<provider>:<model>` string understood by LangChain's `init_chat_model`."""

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(
    ","
)

MAX_COMPANIES = max(1, int(os.environ.get("MAX_COMPANIES", "6")))
"""Most companies a search returns, ranked by fit (score 0-100)."""

MAX_CONCURRENT_SEARCHES = max(1, int(os.environ.get("MAX_CONCURRENT_SEARCHES", "2")))
"""Searches that may run at once (all users). Starting another is refused with HTTP 429, since
they all share one Chrome worker for Google calls and one LLM rate limit."""

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
"""Most ATS boards (any provider) fetched per search (0 turns ATS off)."""

ATS_JOBS_PER_BOARD = max(1, int(os.environ.get("ATS_JOBS_PER_BOARD", "4")))
"""Matching postings kept from each ATS board."""

ATS_RESOLVE_LINKS = max(0, int(os.environ.get("ATS_RESOLVE_LINKS", "3")))
"""Google links resolved per ATS board search when the breadcrumb doesn't show the board."""

USAJOBS_API_KEY = os.environ.get("USAJOBS_API_KEY", "").strip()
"""Free USAJOBS API key (https://developer.usajobs.gov/apirequest). Never log or trace it."""

USAJOBS_EMAIL = os.environ.get("USAJOBS_EMAIL", "").strip()
"""The email the USAJOBS key was registered with (sent as the User-Agent)."""

USAJOBS_MAX_QUERIES = max(0, int(os.environ.get("USAJOBS_MAX_QUERIES", "2")))
"""Most USAJOBS searches per search run (0 turns USAJOBS off)."""

USAJOBS_RESULTS = max(1, min(500, int(os.environ.get("USAJOBS_RESULTS", "10"))))
"""Jobs kept from each USAJOBS search."""


def usajobs_configured() -> bool:
    """True when both USAJOBS credentials are set and the source isn't turned off."""
    return bool(USAJOBS_API_KEY and USAJOBS_EMAIL and USAJOBS_MAX_QUERIES)


LINKEDIN_MESSAGE_MAX_CHARS = max(1, int(os.environ.get("LINKEDIN_MESSAGE_MAX_CHARS", "300")))
"""Upper bound on each person's example LinkedIn connection note (LinkedIn allows 300)."""

DATABASE_DIR = Path(os.environ.get("DATABASE_DIR", PROJECT_DIR.parent / "database"))
"""Local JSON "database" for the POC (to be replaced by Supabase)."""

GOOGLE_RESOLVE_URLS = os.environ.get("GOOGLE_RESOLVE_URLS", "true").lower() != "false"
"""Follow Google's /goto redirects to real URLs (slower, but links are usable)."""

GOOGLE_CACHE_TTL_S = float(os.environ.get("GOOGLE_CACHE_TTL_S", "900"))
"""Seconds a Google results page is reused for a repeated query (0 turns the cache off)."""


FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", PROJECT_DIR / "frontend" / "dist"))
"""Built frontend (`npm run build`) that `server.py` serves at `/` when it exists."""

LLM_USAGE_LOG = Path(os.environ.get("LLM_USAGE_LOG", BACKEND_DIR / "logs" / "llm_usage.csv"))
"""CSV with one row per LLM call (tokens, cost, user); see `llm_usage`."""


def provider_api_key(provider: str) -> str | None:
    """API key for `provider`, accepting this project's `<PROVIDER>_KEY` naming too."""
    name = provider.upper()
    return os.environ.get(f"{name}_API_KEY") or os.environ.get(f"{name}_KEY")


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
"""Supabase project URL. With the two keys below it turns accounts on (see `auth`)."""

SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
"""Public key: password sign-in, token refresh, reading the signed-in user."""

SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
"""Admin key, backend only: creates accounts for valid invite codes. Never send it out."""

COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "auto").strip().lower()
"""Session cookies' `Secure` flag: `auto` (when the request came over HTTPS, including
behind a proxy that sets `X-Forwarded-Proto`), `true` or `false`."""


def auth_enabled() -> bool:
    """True when Supabase is configured: every `/api` call then needs a signed-in user.
    Otherwise (development, tests) everything runs as TEST_USER."""
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY)
