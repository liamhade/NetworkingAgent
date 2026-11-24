"""The user's current search parameters, so the search page can be restored.

Layout: `<DATABASE_DIR>/users/<user_id>/search_params.json`, one object shaped exactly like
`SearchRequest` (background, location, looking_for, boards). Saved when a search is submitted
and (debounced) while the user edits. Named configurations will reuse this shape.

Unlike a search, a draft may be incomplete (empty background / looking_for), so it is
stored as `SearchParams`; `boards` is normalized server-side like in `SearchRequest`.
"""

import threading
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from boards import BoardsConfig, default_config, normalize
from schemas import SearchRequest
from userdata import accounts, storage

_lock = threading.Lock()


class SearchParams(BaseModel):
    """`SearchRequest` with the required text fields allowed to be empty (a draft)."""

    background: str = Field(default="", max_length=20_000)
    location: str = Field(default="", max_length=200)
    looking_for: str = Field(default="", max_length=5_000)
    education: list[str] = Field(default_factory=list, max_length=5)
    boards: BoardsConfig = Field(default_factory=default_config)

    @field_validator("boards", mode="before")
    @classmethod
    def _normalize_boards(cls, value: object) -> BoardsConfig:
        return normalize(value)


def _path(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "search_params.json"


def get(user_id: str) -> SearchParams | None:
    path = _path(user_id)
    with _lock:
        if not path.is_file():
            return None
        try:
            return SearchParams.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # A corrupt file must not take the page down.


def save(user_id: str, params: SearchParams | SearchRequest) -> SearchParams:
    stored = SearchParams.model_validate(params.model_dump())
    with _lock:
        storage.write_atomic(_path(user_id), stored.model_dump(mode="json"))
    return stored
