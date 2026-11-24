"""Invite codes that gate sign-up, kept in `<DATABASE_DIR>/invite_codes.json`.

    python -m auth.invites create --uses 1 --note "alice"   # prints the new code
    python -m auth.invites list
    python -m auth.invites revoke ABCD-EFGH

Run from `backend/src`. In the container (`PYTHONPATH` already points at `src`):
`docker exec <container> python -m auth.invites create --note alice`.
"""

import argparse
import json
import secrets
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

import config

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: codes get read aloud
_lock = threading.Lock()


class InvalidInvite(Exception):
    """The code doesn't exist, was revoked, or has no uses left."""


class Invite(BaseModel):
    code: str
    max_uses: int = 1
    uses: int = 0
    note: str = ""
    created_at: datetime
    revoked: bool = False
    used_by: list[str] = []
    """Supabase user ids that signed up with this code."""

    @property
    def usable(self) -> bool:
        return not self.revoked and self.uses < self.max_uses


def _path() -> Path:
    return Path(config.DATABASE_DIR) / "invite_codes.json"


def _load() -> dict[str, Invite]:
    path = _path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {code: Invite.model_validate(data) for code, data in raw.items()}


def _save(invites: dict[str, Invite]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    data = {code: invite.model_dump(mode="json") for code, invite in invites.items()}
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize(code: str) -> str:
    """Codes are case-insensitive and ignore spaces: `" abcd efgh "` -> `"ABCD-EFGH"`."""
    compact = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{compact[:4]}-{compact[4:]}" if len(compact) == 8 else code.strip().upper()


def create(max_uses: int = 1, note: str = "") -> Invite:
    with _lock:
        invites = _load()
        while True:
            raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
            code = f"{raw[:4]}-{raw[4:]}"
            if code not in invites:
                break
        invite = Invite(
            code=code, max_uses=max(1, max_uses), note=note, created_at=datetime.now(UTC)
        )
        invites[code] = invite
        _save(invites)
        return invite


def reserve(code: str) -> str:
    """Use up one sign-up of `code` and return its normalised form.

    Called before the account is created; `release` gives the use back if that fails.
    """
    key = normalize(code)
    with _lock:
        invites = _load()
        invite = invites.get(key)
        if invite is None or not invite.usable:
            raise InvalidInvite(key)
        invite.uses += 1
        _save(invites)
    return key


def release(code: str) -> None:
    with _lock:
        invites = _load()
        invite = invites.get(code)
        if invite is not None and invite.uses > 0:
            invite.uses -= 1
            _save(invites)


def record_use(code: str, user_id: str) -> None:
    with _lock:
        invites = _load()
        invite = invites.get(code)
        if invite is not None:
            invite.used_by.append(user_id)
            _save(invites)


def revoke(code: str) -> bool:
    key = normalize(code)
    with _lock:
        invites = _load()
        if key not in invites:
            return False
        invites[key].revoked = True
        _save(invites)
        return True


def list_all() -> list[Invite]:
    with _lock:
        return sorted(_load().values(), key=lambda i: i.created_at)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m auth.invites")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create", help="make a new invite code")
    make.add_argument("--uses", type=int, default=1, help="sign-ups it allows (default 1)")
    make.add_argument("--note", default="", help="who it is for")
    sub.add_parser("list", help="show every code")
    gone = sub.add_parser("revoke", help="stop a code from working")
    gone.add_argument("code")
    args = parser.parse_args(argv)

    if args.command == "create":
        invite = create(args.uses, args.note)
        print(invite.code)
    elif args.command == "list":
        for i in list_all():
            state = "revoked" if i.revoked else ("used up" if not i.usable else "open")
            print(f"{i.code}  {i.uses}/{i.max_uses}  {state:8}  {i.note}")
    elif not revoke(args.code):
        print(f"No such code: {args.code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
