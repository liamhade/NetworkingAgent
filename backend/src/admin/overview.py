"""One row per known email (access list + accounts), with that user's LLM usage totals."""

from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel

import config
from auth import access
from llm_usage import recorder, summary
from userdata import accounts


class Usage(BaseModel):
    calls: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    last_used_at: str = ""
    """ISO time of the latest call; empty if none."""


class AdminUser(BaseModel):
    email: str
    """The account email, or the user id when no email is known (e.g. TEST_USER)."""
    status: access.Status | None
    """Access-list status; None for an account that never requested access."""
    is_owner: bool = False
    user_id: str = ""
    requested_at: datetime | None = None
    decided_at: datetime | None = None
    joined_at: datetime | None = None
    """When the account first used the app (its user folder was created)."""
    usage: Usage = Usage()


class AdminOverview(BaseModel):
    owner_email: str
    users: list[AdminUser]
    totals: Usage


def _usage_by_user() -> dict[str, Usage]:
    rows = summary.read_rows(recorder.log_path())
    last: dict[str, str] = defaultdict(str)
    for row in rows:
        uid = row.get("user_id") or "-"
        last[uid] = max(last[uid], row.get("timestamp", ""))
    return {
        str(t["user"]): Usage(
            calls=int(t["calls"]),
            total_tokens=int(t["total_tokens"]),
            cost_usd=float(t["cost_usd"]),
            last_used_at=last[str(t["user"])],
        )
        for t in summary.summarize(rows, ["user"])
    }


def _total(usages: list[Usage]) -> Usage:
    return Usage(
        calls=sum(u.calls for u in usages),
        total_tokens=sum(u.total_tokens for u in usages),
        cost_usd=round(sum(u.cost_usd for u in usages), 6),
        last_used_at=max((u.last_used_at for u in usages), default=""),
    )


_ORDER = {"pending": 0, "approved": 1, "denied": 2, None: 3}


def build() -> AdminOverview:
    """Owner first, then pending requests, approved, denied, never asked; most LLM spend first
    within each."""
    rows: dict[str, AdminUser] = {}
    for entry in access.list_all():
        rows[entry.email] = AdminUser(
            email=entry.email,
            status=entry.status,
            user_id=entry.user_id,
            requested_at=entry.requested_at,
            decided_at=entry.decided_at,
        )

    by_id = {row.user_id: row for row in rows.values() if row.user_id}
    for user in accounts.list_users():
        row = by_id.get(user.id)
        if row is None:
            email = access.normalize(user.display_name) if "@" in user.display_name else user.id
            row = rows.get(email) or AdminUser(email=email, status=None)
            row.user_id = row.user_id or user.id
            rows[email] = row
            by_id[user.id] = row
        row.joined_at = user.created_at

    usage = _usage_by_user()
    for user_id, used in usage.items():
        row = by_id.get(user_id)
        if row is None:  # usage from an id with no account folder left
            row = rows.setdefault(user_id, AdminUser(email=user_id, status=None, user_id=user_id))
            by_id[user_id] = row
        row.usage = used

    if config.OWNER_EMAIL:
        owner = rows.setdefault(
            config.OWNER_EMAIL, AdminUser(email=config.OWNER_EMAIL, status="approved")
        )
        owner.status = "approved"
    for row in rows.values():
        row.is_owner = access.is_owner(row.email)

    ordered = sorted(
        rows.values(),
        key=lambda r: (not r.is_owner, _ORDER[r.status], -r.usage.cost_usd, r.email),
    )
    return AdminOverview(
        owner_email=config.OWNER_EMAIL,
        users=ordered,
        totals=_total([r.usage for r in ordered]),
    )
