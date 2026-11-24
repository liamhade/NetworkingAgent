"""Sessions in HttpOnly cookies, and who is making each request.

`SessionMiddleware` reads the cookies on every `/api` request (except `/api/auth/*`, which
set them), finds the signed-in Supabase user, checks the owner approved them (`access`),
refreshes an expired access token with the refresh cookie, and re-sets the cookies on the
response. It is middleware, not a
dependency, because a dependency can't add cookies to a `StreamingResponse`.
`current_user` is the FastAPI dependency the endpoints use.
"""

import hashlib
import threading
import time
from typing import Any

import anyio
from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import config
from userdata import accounts

from . import access, supabase
from .supabase import AuthError, Session, SupabaseUser

ACCESS_COOKIE = "na_access"
REFRESH_COOKIE = "na_refresh"
REFRESH_MAX_AGE_S = 30 * 24 * 3600
VERIFIED_TTL_S = 60.0
"""How long a checked access token is trusted before asking Supabase again."""

_STATE_KEY = "auth_user"
_verified: dict[str, tuple[float, SupabaseUser]] = {}
_verified_lock = threading.Lock()


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_for_token(token: str) -> SupabaseUser | None:
    """The user behind an access token (cached for `VERIFIED_TTL_S`), or None."""
    key = _token_key(token)
    now = time.monotonic()
    with _verified_lock:
        hit = _verified.get(key)
        if hit is not None and hit[0] > now:
            return hit[1]
    user = supabase.get_user(token)
    if user is not None:
        with _verified_lock:
            if len(_verified) > 1000:
                _verified.clear()
            _verified[key] = (now + VERIFIED_TTL_S, user)
    return user


def forget_token(token: str) -> None:
    with _verified_lock:
        _verified.pop(_token_key(token), None)


def is_secure(request: Request) -> bool:
    if config.COOKIE_SECURE in ("true", "false"):
        return config.COOKIE_SECURE == "true"
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return (forwarded or request.url.scheme) == "https"


def set_session_cookies(response: Response, session: Session, secure: bool) -> None:
    common: dict[str, Any] = {"httponly": True, "samesite": "lax", "secure": secure, "path": "/"}
    response.set_cookie(ACCESS_COOKIE, session.access_token, max_age=session.expires_in, **common)
    response.set_cookie(REFRESH_COOKIE, session.refresh_token, max_age=REFRESH_MAX_AGE_S, **common)


def clear_session_cookies(response: Response, secure: bool) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/", secure=secure, httponly=True, samesite="lax")


_CLEAR = object()
"""`_resolve` result: the refresh token is dead, so drop both cookies."""


def _resolve(access: str | None, refresh: str | None) -> tuple[SupabaseUser | None, Any]:
    """(user, new session | _CLEAR | None) from the request's cookies. Blocking."""
    if access:
        user = user_for_token(access)
        if user is not None:
            return user, None
    if refresh:
        try:
            session = supabase.refresh(refresh)
        except AuthError as exc:
            if exc.status == 401:
                return None, _CLEAR
            raise
        return session.user, session
    return None, None


def _resolve_approved(token: str | None, refresh: str | None) -> tuple[SupabaseUser | None, Any]:
    """`_resolve`, except a user the owner hasn't approved counts as signed out.

    Checked on every request (not cached) so `deny` works at once, and so a token taken
    straight from Supabase with the public anon key can't skip the approval.
    """
    user, change = _resolve(token, refresh)
    if user is not None and access.status_of(user.id, user.email) != "approved":
        user = None
    return user, change


class SessionMiddleware:
    """Pure ASGI, so streamed responses (search events) pass through untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not config.auth_enabled()
            or not path.startswith("/api/")
            or path.startswith("/api/auth/")
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        try:
            user, change = await anyio.to_thread.run_sync(
                _resolve_approved,
                request.cookies.get(ACCESS_COOKIE),
                request.cookies.get(REFRESH_COOKIE),
            )
        except AuthError as exc:  # Supabase is down: say so rather than "signed out"
            response = JSONResponse({"detail": exc.message}, exc.status)
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})[_STATE_KEY] = user

        cookies: list[str] = []
        if change is not None:
            holder = Response()
            if change is _CLEAR:
                clear_session_cookies(holder, is_secure(request))
            else:
                set_session_cookies(holder, change, is_secure(request))
            cookies = holder.headers.getlist("set-cookie")

        async def send_with_cookies(message: Message) -> None:
            if message["type"] == "http.response.start" and cookies:
                headers = MutableHeaders(scope=message)
                for cookie in cookies:
                    headers.append("set-cookie", cookie)
            await send(message)

        await self.app(scope, receive, send_with_cookies)


def current_user(request: Request) -> accounts.User:
    """FastAPI dependency: the signed-in user (401 if none), or TEST_USER without auth."""
    if not config.auth_enabled():
        return accounts.get_current_user()
    user: SupabaseUser | None = request.scope.get("state", {}).get(_STATE_KEY)
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return accounts.ensure_user(user.id, user.email or user.id)


def is_admin(request: Request) -> bool:
    """True for the owner (`OWNER_EMAIL`). Without accounts (local development, where everyone
    is TEST_USER and the server is open anyway) everyone is: the Admin tab can be tried."""
    if not config.auth_enabled():
        return True
    user: SupabaseUser | None = request.scope.get("state", {}).get(_STATE_KEY)
    return user is not None and access.is_owner(user.email)


def require_admin(request: Request) -> None:
    """FastAPI dependency for the owner-only `/api/admin` endpoints (401 signed out, else 403)."""
    if config.auth_enabled() and request.scope.get("state", {}).get(_STATE_KEY) is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Only the owner can open the admin page.")
