"""Search history, stored as JSON files under the local `database/` folder.

Layout: `<DATABASE_DIR>/users/<user_id>/searches/<search_id>.json`, one `SavedSearch` per
file (the user folder comes from `accounts.user_dir`). This is a POC stand-in for Supabase;
keep all search-history storage access in this module.
"""

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from schemas import SavedSearch, SearchRequest, SearchResults, SearchSummary
from userdata import accounts

TITLE_MAX_CHARS = 40
LOCATION_MAX_CHARS = 24
_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_FILLER = re.compile(
    r"^(?:i\s*(?:'m|am)\s+|i\s+(?:want|would like|'d like)\s+(?:to\s+)?|"
    r"(?:currently\s+)?(?:looking|searching|hoping)\s+(?:for|to)\s+|to\s+find\s+|"
    r"find\s+|a\s+|an\s+|some\s+)+",
    re.IGNORECASE,
)


def _searches_dir(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "searches"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit + 1].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(" ,;:-") + "…"


def make_title(request: SearchRequest) -> str:
    """Short, human title for a search, derived from its inputs (no LLM call)."""
    text = " ".join(request.looking_for.split())
    text = re.split(r"(?<=[.!?;])\s|[.!?;]$", text, maxsplit=1)[0].rstrip(".!?;")
    text = _FILLER.sub("", text + " ").strip() or "Search"
    title = _truncate(text[0].upper() + text[1:], TITLE_MAX_CHARS)
    location = " ".join(request.location.split())
    if location:
        title += f" · {_truncate(location, LOCATION_MAX_CHARS)}"
    return title


def save_search(user_id: str, request: SearchRequest, results: SearchResults) -> SavedSearch:
    """Persist a finished search for `user_id` and return the stored record."""
    record = SavedSearch(
        id=uuid.uuid4().hex,
        user_id=user_id,
        created_at=datetime.now(UTC),
        title=make_title(request),
        request=request,
        results=results,
    )
    folder = _searches_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record.id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return record


def list_searches(user_id: str) -> list[SearchSummary]:
    """All of a user's searches, most recent first."""
    folder = _searches_dir(user_id)
    if not folder.is_dir():
        return []
    summaries = []
    for path in folder.glob("*.json"):
        try:
            record = SavedSearch.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # Skip unreadable/corrupt files rather than breaking the panel.
        summaries.append(
            SearchSummary(id=record.id, title=record.title, created_at=record.created_at)
        )
    summaries.sort(key=lambda summary: summary.created_at, reverse=True)
    return summaries


def get_search(user_id: str, search_id: str) -> SavedSearch | None:
    """One of a user's saved searches, or None if missing (or the id is malformed)."""
    if not _ID_PATTERN.match(search_id):
        return None
    path = _searches_dir(user_id) / f"{search_id}.json"
    if not path.is_file():
        return None
    return SavedSearch.model_validate_json(path.read_text(encoding="utf-8"))
