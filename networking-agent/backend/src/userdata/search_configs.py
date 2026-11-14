"""Named, saved search configurations, persisted per user.

Layout: `<DATABASE_DIR>/users/<user_id>/search_configs.json`:

    {"counter": 3, "configs": [{"id", "name", "params": SearchParams, "created_at",
                                "updated_at"}, ...]}

`configs` is in creation order. `counter` is the highest "Search Configuration #n" number ever
handed out, so default names are never reused after a delete. Keep all access to this
storage in this module (Supabase later).
"""

import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from userdata import accounts, storage
from userdata.search_params import SearchParams

MAX_NAME_LENGTH = 80
DEFAULT_PREFIX = "Search Configuration #"
_DEFAULT_NAME = re.compile(rf"^{re.escape(DEFAULT_PREFIX)}(\d+)$")
_lock = threading.Lock()


class InvalidName(ValueError):
    pass


class SearchConfig(BaseModel):
    id: str
    name: str
    params: SearchParams
    created_at: datetime
    updated_at: datetime


def _path(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "search_configs.json"


def _read(user_id: str) -> tuple[int, list[SearchConfig]]:
    path = _path(user_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        configs = [SearchConfig.model_validate(item) for item in data.get("configs", [])]
        return int(data.get("counter", 0)), configs
    except (OSError, ValueError, AttributeError, TypeError):
        return 0, []  # A corrupt file must not take the page down.


def _write(user_id: str, counter: int, configs: list[SearchConfig]) -> None:
    storage.write_atomic(
        _path(user_id),
        {"counter": counter, "configs": [c.model_dump(mode="json") for c in configs]},
    )


def clean_name(name: str) -> str:
    """Trim `name`; reject empty and over-long names."""
    cleaned = name.strip()
    if not cleaned:
        raise InvalidName("Name must not be empty.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise InvalidName(f"Name must be at most {MAX_NAME_LENGTH} characters.")
    return cleaned


def _highest_default(counter: int, configs: list[SearchConfig]) -> int:
    numbers = [int(m.group(1)) for c in configs if (m := _DEFAULT_NAME.match(c.name))]
    return max([counter, *numbers])


def list_configs(user_id: str) -> list[SearchConfig]:
    with _lock:
        return _read(user_id)[1]


def get_config(user_id: str, config_id: str) -> SearchConfig | None:
    return next((c for c in list_configs(user_id) if c.id == config_id), None)


def create(user_id: str, params: SearchParams, name: str | None = None) -> SearchConfig:
    """Save `params`. Without a name, use the next unused "Search Configuration #n"."""
    now = datetime.now(UTC)
    with _lock:
        counter, configs = _read(user_id)
        if name is None:
            counter = _highest_default(counter, configs) + 1
            name = f"{DEFAULT_PREFIX}{counter}"
        else:
            name = clean_name(name)
            counter = _highest_default(counter, configs)
        config = SearchConfig(
            id=uuid.uuid4().hex,
            name=name,
            params=SearchParams.model_validate(params.model_dump()),
            created_at=now,
            updated_at=now,
        )
        _write(user_id, counter, [*configs, config])
    return config


def update(
    user_id: str,
    config_id: str,
    name: str | None = None,
    params: SearchParams | None = None,
) -> SearchConfig | None:
    """Rename and/or overwrite the params; `None` when the id is unknown."""
    cleaned = clean_name(name) if name is not None else None
    with _lock:
        counter, configs = _read(user_id)
        for index, config in enumerate(configs):
            if config.id != config_id:
                continue
            changes: dict = {"updated_at": datetime.now(UTC)}
            if cleaned is not None:
                changes["name"] = cleaned
            if params is not None:
                changes["params"] = SearchParams.model_validate(params.model_dump())
            configs[index] = config.model_copy(update=changes)
            _write(user_id, _highest_default(counter, configs), configs)
            return configs[index]
    return None


def delete(user_id: str, config_id: str) -> bool:
    with _lock:
        counter, configs = _read(user_id)
        kept = [c for c in configs if c.id != config_id]
        if len(kept) == len(configs):
            return False
        # Persist the high-water mark first so the deleted number is never reused.
        _write(user_id, _highest_default(counter, configs), kept)
    return True
