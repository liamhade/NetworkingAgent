"""Search history, stored as JSON files under the local `database/` folder.

Layout: `<DATABASE_DIR>/users/<user_id>/searches/<search_id>.json`, one `SavedSearch` per
file (the user folder comes from `accounts.user_dir`). This is a POC stand-in for Supabase;
keep all search-history storage access in this module.
"""

import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from schemas import SavedSearch, SearchRequest, SearchResults, SearchSummary, TraceStep
from userdata import accounts

TITLE_MAX_CHARS = 32
LOCATION_MAX_CHARS = 20
_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_FILLER = re.compile(
    r"^(?:i\s*(?:'m|am)\s+|i\s+(?:want|would like|'d like)\s+(?:to\s+)?|"
    r"(?:currently\s+)?(?:looking|searching|hoping)\s+(?:for|to)\s+|to\s+find\s+|"
    r"find\s+|a\s+|an\s+|some\s+)+",
    re.IGNORECASE,
)
# Where a request turns from "what" into qualifiers: "roles, particularly in fintech".
_QUALIFIER = re.compile(
    r"\s*(?:[,(:\u2013\u2014]|\s-\s|\s(?:particularly|especially|ideally|preferably|mainly|"
    r"mostly|primarily|specifically|such as|including|like|with|that|which|where|who|"
    r"focused|focusing|in|at|for|on|within|near|around|across|using)\b)",
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
    head = _QUALIFIER.split(text, maxsplit=1)[0].strip()
    if len(head.split()) >= 2:  # Keep the core noun phrase, drop the qualifiers.
        text = head
    title = _truncate(text[0].upper() + text[1:], TITLE_MAX_CHARS)
    location = " ".join(request.location.split())
    if location:
        title += f" · {_truncate(location, LOCATION_MAX_CHARS)}"
    return title


def new_search_id() -> str:
    return uuid.uuid4().hex


def save_search(
    user_id: str,
    request: SearchRequest,
    results: SearchResults,
    search_id: str | None = None,
    trace: list[TraceStep] | None = None,
) -> SavedSearch:
    """Persist a finished search for `user_id` and return the stored record.

    `search_id` lets the caller pick the id up front (so LLM usage logs can reference it).
    `trace` records how the results were found (see `pipeline`).
    """
    if search_id is not None and not _ID_PATTERN.match(search_id):
        raise ValueError(f"Invalid search id: {search_id!r}")
    record = SavedSearch(
        id=search_id or new_search_id(),
        user_id=user_id,
        created_at=datetime.now(UTC),
        title=make_title(request),
        request=request,
        results=results,
        trace=trace,
    )
    _write(record)
    return record


def start_search(user_id: str, request: SearchRequest, search_id: str) -> SavedSearch:
    """Persist a search that is about to run in the background (status `running`)."""
    if not _ID_PATTERN.match(search_id):
        raise ValueError(f"Invalid search id: {search_id!r}")
    record = SavedSearch(
        id=search_id,
        user_id=user_id,
        created_at=datetime.now(UTC),
        title=make_title(request),
        request=request,
        status="running",
    )
    _write(record)
    return record


def add_message(user_id: str, search_id: str, message: str) -> None:
    """Append a progress message to a running search."""
    update_search(
        user_id, search_id, lambda r: r.model_copy(update={"messages": [*r.messages, message]})
    )


def finish_search(
    user_id: str, search_id: str, results: SearchResults, trace: list[TraceStep] | None
) -> SavedSearch | None:
    """Mark a running search done and store its results."""
    return update_search(
        user_id,
        search_id,
        lambda r: r.model_copy(
            update={"status": "done", "results": results, "trace": trace, "error": None}
        ),
    )


def fail_search(user_id: str, search_id: str, message: str) -> SavedSearch | None:
    """Mark a running search failed, keeping the reason."""
    return update_search(
        user_id,
        search_id,
        lambda r: r.model_copy(update={"status": "error", "error": message}),
    )


def cancel_search(user_id: str, search_id: str) -> SavedSearch | None:
    """Mark a running search cancelled (a no-op for one that already ended)."""
    return update_search(
        user_id,
        search_id,
        lambda r: (
            r.model_copy(update={"status": "cancelled", "error": None})
            if r.status == "running"
            else r
        ),
    )


class SearchRunning(RuntimeError):
    """The search is still running, so it cannot be deleted (cancel it first)."""


def delete_search(user_id: str, search_id: str) -> bool:
    """Remove a saved search; False if it doesn't exist. Raises `SearchRunning` if running.

    Runs under the same per-search lock as `update_search`, so a late write from a worker
    or an on-demand people search can never resurrect the file (they find no record).
    """
    if not _ID_PATTERN.match(search_id):
        return False
    with _lock(user_id, search_id):
        record = get_search(user_id, search_id)
        if record is None:
            return False
        if record.status == "running":
            raise SearchRunning(search_id)
        path = _searches_dir(user_id) / f"{search_id}.json"
        for attempt in range(5):
            try:
                path.unlink(missing_ok=True)
                break
            except PermissionError:
                # Windows refuses to delete a file another thread is reading; retry briefly.
                if attempt == 4:
                    raise
                time.sleep(0.05)
    with _locks_guard:
        _locks.pop((user_id, search_id), None)
    return True


INTERRUPTED_MESSAGE = "This search was interrupted because the server restarted. Run it again."


def mark_interrupted() -> int:
    """At startup no search can still be running: flag stale `running` records as failed.

    Covers every user. Returns how many records were changed.
    """
    changed = 0
    users = accounts.users_dir()
    if not users.is_dir():
        return 0
    for folder in users.iterdir():
        if not folder.is_dir():
            continue
        try:
            records = load_searches(folder.name)
        except ValueError:
            continue
        for record in records:
            if record.status == "running":
                fail_search(folder.name, record.id, INTERRUPTED_MESSAGE)
                changed += 1
    return changed


def _write(record: SavedSearch) -> None:
    folder = _searches_dir(record.user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record.id}.json"
    tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            # Windows refuses to replace a file another thread is reading; retry briefly.
            if attempt == 4:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)


_locks: dict[tuple[str, str], threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock(user_id: str, search_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault((user_id, search_id), threading.Lock())


def update_search(
    user_id: str, search_id: str, change: Callable[[SavedSearch], SavedSearch]
) -> SavedSearch | None:
    """Apply `change` to a saved search and store the result; None if it doesn't exist.

    The read-modify-write runs under a per-search lock, so concurrent updates of the same
    search (e.g. two on-demand people searches) never overwrite each other. Different
    searches don't block each other. Keep `change` fast: it runs while holding the lock.
    """
    with _lock(user_id, search_id):
        record = get_search(user_id, search_id)
        if record is None:
            return None
        updated = change(record)
        _write(updated)
        return updated


def load_searches(user_id: str, only_done: bool = False) -> list[SavedSearch]:
    """All of a user's saved searches (full records), most recent first.

    `only_done` skips searches that are still running or failed (they have no results).
    """
    folder = _searches_dir(user_id)
    if not folder.is_dir():
        return []
    records = []
    for path in folder.glob("*.json"):
        try:
            record = _read(path)
        except (OSError, ValueError):
            continue  # Skip unreadable/corrupt files rather than breaking the page.
        if not only_done or record.status == "done":
            records.append(record)
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


def list_searches(user_id: str) -> list[SearchSummary]:
    """All of a user's searches, most recent first."""
    return [
        SearchSummary(
            id=record.id, title=record.title, created_at=record.created_at, status=record.status
        )
        for record in load_searches(user_id)
    ]


def get_search(user_id: str, search_id: str) -> SavedSearch | None:
    """One of a user's saved searches, or None if missing (or the id is malformed)."""
    if not _ID_PATTERN.match(search_id):
        return None
    path = _searches_dir(user_id) / f"{search_id}.json"
    if not path.is_file():
        return None
    return _read(path)


def _read(path: Path) -> SavedSearch:
    """Load a record, re-deriving its title so older searches get the current title style."""
    record = SavedSearch.model_validate_json(path.read_text(encoding="utf-8"))
    return record.model_copy(update={"title": make_title(record.request)})
