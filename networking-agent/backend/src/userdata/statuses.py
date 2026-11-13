"""APPLIED / CONNECTED toggles, persisted per user across searches.

Layout: `<DATABASE_DIR>/users/<user_id>/statuses.json`:

    {"job": {"<entity key>": {"active": true, "updated_at": "..."}}, "person": {...}}

Entries are keyed by `entities.keys` (stable across searches), so a job marked APPLIED stays
APPLIED whenever it shows up again. Turning a toggle off keeps the entry with
`active: false`. Keep all status storage access in this module (Supabase later).
"""

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from schemas import EntityStatus, EntityStatusKind, StatusUpdate
from userdata import accounts, storage

KINDS: tuple[EntityStatusKind, ...] = get_args(EntityStatusKind)
_lock = threading.Lock()  # Endpoints run in a thread pool; serialize read-modify-write.


class InvalidStatusKey(ValueError):
    pass


def _path(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "statuses.json"


def _load(user_id: str) -> dict[str, dict[str, dict]]:
    return storage.read_keyed(_path(user_id), KINDS)


def get_statuses(user_id: str) -> dict[EntityStatusKind, dict[str, bool]]:
    """`{kind: {key: active}}` for every toggle the user has ever set."""
    with _lock:
        data = _load(user_id)
    return {
        kind: {key: bool(entry.get("active")) for key, entry in entries.items()}
        for kind, entries in data.items()
    }


def set_status(user_id: str, update: StatusUpdate) -> EntityStatus:
    """Set (not flip) one toggle, so repeated or out-of-order requests converge."""
    if not update.key.startswith(f"{update.kind}:"):
        raise InvalidStatusKey(f"Key {update.key!r} is not a {update.kind} key.")
    status = EntityStatus(**update.model_dump(), updated_at=datetime.now(UTC))
    with _lock:
        data = _load(user_id)
        data[update.kind][update.key] = {
            "active": status.active,
            "updated_at": status.updated_at.isoformat(),
        }
        storage.write_atomic(_path(user_id), data)
    return status
