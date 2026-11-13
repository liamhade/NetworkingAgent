"""Minimal account layer for the POC (no auth yet).

Users are stored as `<DATABASE_DIR>/users/<user_id>/user.json`; every piece of per-user
data lives next to it under `<DATABASE_DIR>/users/<user_id>/...` (see `user_dir`).

`get_current_user` is the single place that decides who is making a request. It always
returns TEST_USER for now; real auth (e.g. a Supabase JWT) plugs in there later.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

import config

TEST_USER_ID = "TEST_USER"
TEST_USER_NAME = "Test User"
_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class User(BaseModel):
    id: str
    display_name: str
    created_at: datetime


def users_dir() -> Path:
    return Path(config.DATABASE_DIR) / "users"


def user_dir(user_id: str) -> Path:
    """Root folder for one user's data. Rejects ids that could escape `users/`."""
    if not _USER_ID_PATTERN.match(user_id):
        raise ValueError(f"Invalid user id: {user_id!r}")
    return users_dir() / user_id


def get_user(user_id: str) -> User | None:
    path = user_dir(user_id) / "user.json"
    if not path.is_file():
        return None
    return User.model_validate_json(path.read_text(encoding="utf-8"))


def ensure_user(user_id: str, display_name: str) -> User:
    """Return the user, creating their record on first use."""
    existing = get_user(user_id)
    if existing is not None:
        return existing
    user = User(id=user_id, display_name=display_name, created_at=datetime.now(UTC))
    folder = user_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "user.json").write_text(user.model_dump_json(indent=2), encoding="utf-8")
    return user


def seed() -> None:
    """Make sure the TEST_USER account exists."""
    ensure_user(TEST_USER_ID, TEST_USER_NAME)


def get_current_user() -> User:
    """Who is making this request. FastAPI dependency; always TEST_USER until auth exists."""
    return ensure_user(TEST_USER_ID, TEST_USER_NAME)
