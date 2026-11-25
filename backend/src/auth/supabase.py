"""The Supabase Auth REST calls the app needs, with `requests` (no Supabase SDK).

Public calls (`apikey` = anon key): password sign-in, refresh, read the signed-in user,
sign out. Admin calls (service-role key, backend only): create, find and delete users, and
set a password.
Docs: https://supabase.com/docs/reference/api (GoTrue `/auth/v1/...`).
"""

import logging
from dataclasses import dataclass
from typing import Any

import requests

import config

log = logging.getLogger(__name__)

TIMEOUT_S = 10.0


class AuthError(Exception):
    """A sign-in or sign-up problem; `message` is safe to show the user."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class SupabaseUser:
    id: str
    email: str


@dataclass(frozen=True)
class Session:
    access_token: str
    refresh_token: str
    expires_in: int
    """Seconds the access token is valid for."""
    user: SupabaseUser


def _url(path: str) -> str:
    return f"{config.SUPABASE_URL}/auth/v1/{path}"


def _public_headers(access_token: str | None = None) -> dict[str, str]:
    headers = {"apikey": config.SUPABASE_ANON_KEY}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _admin_headers() -> dict[str, str]:
    key = config.SUPABASE_SERVICE_ROLE_KEY
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _body(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _message(body: dict[str, Any]) -> str:
    """Supabase's error text; older and newer endpoints use different fields."""
    for key in ("msg", "error_description", "message", "error"):
        if isinstance(body.get(key), str) and body[key]:
            return body[key]
    return ""


def _user(data: dict[str, Any]) -> SupabaseUser:
    return SupabaseUser(id=str(data["id"]), email=str(data.get("email") or ""))


def _session(response: requests.Response) -> Session:
    data = _body(response)
    return Session(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=int(data.get("expires_in") or 3600),
        user=_user(data["user"]),
    )


def _unavailable(response: requests.Response) -> AuthError:
    log.warning("Supabase Auth returned %s: %s", response.status_code, response.text[:300])
    return AuthError(502, "Sign-in is unavailable right now. Please try again in a minute.")


def password_login(email: str, password: str) -> Session:
    response = requests.post(
        _url("token?grant_type=password"),
        json={"email": email, "password": password},
        headers=_public_headers(),
        timeout=TIMEOUT_S,
    )
    if response.status_code == 200:
        return _session(response)
    if response.status_code in (400, 401):
        raise AuthError(401, "Wrong email or password.")
    if response.status_code == 429:
        raise AuthError(429, "Too many sign-in attempts. Please wait a minute and try again.")
    raise _unavailable(response)


def refresh(refresh_token: str) -> Session:
    """A new session for a refresh token; `AuthError(401)` if it was revoked or expired."""
    response = requests.post(
        _url("token?grant_type=refresh_token"),
        json={"refresh_token": refresh_token},
        headers=_public_headers(),
        timeout=TIMEOUT_S,
    )
    if response.status_code == 200:
        return _session(response)
    if response.status_code in (400, 401, 403):
        raise AuthError(401, "Your session has ended. Please sign in again.")
    raise _unavailable(response)


def get_user(access_token: str) -> SupabaseUser | None:
    """The user an access token belongs to; None if it is invalid or expired."""
    response = requests.get(_url("user"), headers=_public_headers(access_token), timeout=TIMEOUT_S)
    if response.status_code == 200:
        return _user(_body(response))
    if response.status_code in (401, 403):
        return None
    raise _unavailable(response)


def logout(access_token: str) -> None:
    """Revoke the session's refresh tokens. Best effort: never raises."""
    try:
        requests.post(_url("logout"), headers=_public_headers(access_token), timeout=TIMEOUT_S)
    except requests.RequestException:
        log.info("Supabase logout failed", exc_info=True)


def admin_create_user(email: str, password: str) -> SupabaseUser:
    """Create a confirmed account. The app only lets it in once the owner approves the email
    (`auth.access`), so Supabase's own confirmation email isn't needed."""
    response = requests.post(
        _url("admin/users"),
        json={"email": email, "password": password, "email_confirm": True},
        headers=_admin_headers(),
        timeout=TIMEOUT_S,
    )
    if response.status_code in (200, 201):
        return _user(_body(response))
    body = _body(response)
    code = str(body.get("error_code") or body.get("code") or "")
    message = _message(body)
    if code == "email_exists" or "already been registered" in message:
        raise AuthError(409, "An account with this email already exists. Sign in instead.")
    if response.status_code in (400, 422):
        raise AuthError(400, message or "That email or password isn't accepted.")
    raise _unavailable(response)


def admin_delete_user(user_id: str) -> None:
    response = requests.delete(
        _url(f"admin/users/{user_id}"), headers=_admin_headers(), timeout=TIMEOUT_S
    )
    if response.status_code not in (200, 204, 404):
        raise _unavailable(response)


def admin_set_password(user_id: str, password: str) -> None:
    """Set an account's password (no email, no old password needed)."""
    response = requests.put(
        _url(f"admin/users/{user_id}"),
        json={"password": password},
        headers=_admin_headers(),
        timeout=TIMEOUT_S,
    )
    if response.status_code == 200:
        return
    if response.status_code == 404:
        raise AuthError(404, "There is no account with this email.")
    if response.status_code in (400, 422):
        raise AuthError(400, _message(_body(response)) or "That password isn't accepted.")
    raise _unavailable(response)


ADMIN_PAGE_SIZE = 1000


def admin_find_user(email: str) -> SupabaseUser | None:
    """The account with this email (case-insensitive), by paging through every user."""
    wanted = email.strip().lower()
    page = 1
    while True:
        response = requests.get(
            _url("admin/users"),
            params={"page": page, "per_page": ADMIN_PAGE_SIZE},
            headers=_admin_headers(),
            timeout=TIMEOUT_S,
        )
        if response.status_code != 200:
            raise _unavailable(response)
        users = _body(response).get("users") or []
        for data in users:
            if str(data.get("email") or "").lower() == wanted:
                return _user(data)
        if len(users) < ADMIN_PAGE_SIZE:
            return None
        page += 1
