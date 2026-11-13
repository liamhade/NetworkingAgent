"""Pinned ("come back to later") companies, jobs and people, persisted per user.

Layout: `<DATABASE_DIR>/users/<user_id>/pins.json`:

    {"company": {"<entity key>": {"pinned": true, "updated_at": "..."}}, "job": {...},
     "person": {...}}

Entries are keyed by `entities.keys`, so a pin follows the entity into later searches and
onto the Companies / Jobs / People pages. Unpinning keeps the entry with `pinned: false`.
Keep all pin storage access in this module (Supabase later).
"""

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from schemas import EntityPin, PinKind, PinUpdate
from userdata import accounts, storage

KINDS: tuple[PinKind, ...] = get_args(PinKind)
_lock = threading.Lock()  # Endpoints run in a thread pool; serialize read-modify-write.


class InvalidPinKey(ValueError):
    pass


def _path(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "pins.json"


def get_pins(user_id: str) -> dict[PinKind, dict[str, bool]]:
    """`{kind: {key: pinned}}` for every pin the user has ever set."""
    with _lock:
        data = storage.read_keyed(_path(user_id), KINDS)
    return {
        kind: {key: bool(entry.get("pinned")) for key, entry in entries.items()}
        for kind, entries in data.items()
    }


def set_pin(user_id: str, update: PinUpdate) -> EntityPin:
    """Set (not flip) one pin, so repeated or out-of-order requests converge."""
    if not update.key.startswith(f"{update.kind}:"):
        raise InvalidPinKey(f"Key {update.key!r} is not a {update.kind} key.")
    pin = EntityPin(**update.model_dump(), updated_at=datetime.now(UTC))
    with _lock:
        data = storage.read_keyed(_path(user_id), KINDS)
        data[update.kind][update.key] = {
            "pinned": pin.pinned,
            "updated_at": pin.updated_at.isoformat(),
        }
        storage.write_atomic(_path(user_id), data)
    return pin
