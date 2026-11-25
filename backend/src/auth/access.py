"""Who may use the app: emails the owner approved, kept in `<DATABASE_DIR>/access.json`.

People request access on the sign-in page, then email `ACCESS_REQUEST_EMAIL` from that
address; the owner checks the sender and approves. Plan: `docs/access-requests/plan.md`.

    python -m auth.access list               # pending first
    python -m auth.access approve a@x.com    # also pre-approves an email that hasn't asked
    python -m auth.access deny a@x.com       # blocks it (pending or approved)
    python -m auth.access reset-password a@x.com  # prints a new temporary password

The same actions are on the owner's Admin tab (`admin`). `OWNER_EMAIL` is always approved.
Run from `backend/src`. In the container (`PYTHONPATH` already points at `src`):
`railway ssh -- python -m auth.access approve a@x.com`.
"""

import argparse
import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

import config

Status = Literal["pending", "approved", "denied"]
_lock = threading.Lock()


class Entry(BaseModel):
    email: str
    status: Status
    user_id: str = ""
    """Supabase user id, once the person has requested access."""
    requested_at: datetime | None = None
    decided_at: datetime | None = None


def normalize(email: str) -> str:
    return email.strip().lower()


def _path() -> Path:
    return Path(config.DATABASE_DIR) / "access.json"


def _load() -> dict[str, Entry]:
    path = _path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {email: Entry.model_validate(data) for email, data in raw.items()}


def _save(entries: dict[str, Entry]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    data = {email: entry.model_dump(mode="json") for email, entry in entries.items()}
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _now() -> datetime:
    return datetime.now(UTC)


def is_owner(email: str) -> bool:
    """True for `OWNER_EMAIL`, who is always let in and can't be denied."""
    return bool(config.OWNER_EMAIL) and normalize(email) == config.OWNER_EMAIL


def get(email: str) -> Entry | None:
    with _lock:
        return _load().get(normalize(email))


def request(email: str, user_id: str) -> Entry:
    """Record a request for a new account. Pre-approved emails come back approved."""
    key = normalize(email)
    with _lock:
        entries = _load()
        entry = entries.get(key)
        if entry is None:
            entry = Entry(email=key, status="approved" if is_owner(key) else "pending")
            entries[key] = entry
        if is_owner(key):
            entry.status = "approved"
        entry.user_id = user_id
        entry.requested_at = _now()
        _save(entries)
        return entry


def _decide(email: str, status: Status) -> Entry:
    key = normalize(email)
    with _lock:
        entries = _load()
        entry = entries.setdefault(key, Entry(email=key, status=status))
        entry.status = status
        entry.decided_at = _now()
        _save(entries)
        return entry


def approve(email: str) -> Entry:
    return _decide(email, "approved")


def deny(email: str) -> Entry:
    """Block an email. Raises `ValueError` for the owner, who can't be locked out."""
    if is_owner(email):
        raise ValueError("The owner's email can't be removed from the whitelist.")
    return _decide(email, "denied")


def list_all() -> list[Entry]:
    order = {"pending": 0, "approved": 1, "denied": 2}
    with _lock:
        entries = _load().values()
    oldest = datetime.min.replace(tzinfo=UTC)
    return sorted(entries, key=lambda e: (order[e.status], e.requested_at or oldest, e.email))


def _legacy_invite_user_ids() -> set[str]:
    """Supabase ids that signed up with an invite code, before access requests existed."""
    path = Path(config.DATABASE_DIR) / "invite_codes.json"
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {uid for invite in raw.values() for uid in invite.get("used_by", [])}
    except (ValueError, AttributeError):
        return set()


def status_of(user_id: str, email: str) -> Status | None:
    """The access status of a signed-in Supabase user (None: never requested access)."""
    key = normalize(email)
    if is_owner(key):
        return "approved"
    with _lock:
        entries = _load()
        entry = entries.get(key)
        if entry is not None:
            return entry.status
        if user_id and user_id in _legacy_invite_user_ids():
            entries[key] = Entry(email=key, status="approved", user_id=user_id, decided_at=_now())
            _save(entries)
            return "approved"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m auth.access")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show every request, pending first")
    for name, text in (
        ("approve", "let this email in"),
        ("deny", "block this email"),
        ("reset-password", "give this account a new temporary password (also the owner's)"),
    ):
        sub.add_parser(name, help=text).add_argument("email")
    args = parser.parse_args(argv)

    if args.command == "list":
        entries = list_all()
        if not entries:
            print("No access requests yet.")
        for e in entries:
            when = e.requested_at.strftime("%Y-%m-%d %H:%M") if e.requested_at else "not requested"
            print(f"{e.status:8}  {e.email:40}  {when}")
        return 0
    if "@" not in args.email:
        print(f"Not an email address: {args.email}", file=sys.stderr)
        return 1
    if args.command == "reset-password":
        from . import passwords, supabase

        if not config.auth_enabled():
            print("Accounts are off (no Supabase settings): there's no password.", file=sys.stderr)
            return 1
        try:
            password = passwords.reset(args.email)
        except supabase.AuthError as exc:
            print(exc.message, file=sys.stderr)
            return 1
        print(f"{normalize(args.email)}: new temporary password: {password}")
        print("Sign in with it, then change it from the top bar (Change password).")
        return 0
    try:
        entry = approve(args.email) if args.command == "approve" else deny(args.email)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    signed_up = "" if entry.user_id else " (no account yet: their request will be approved at once)"
    print(f"{entry.email}: {entry.status}{signed_up}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
