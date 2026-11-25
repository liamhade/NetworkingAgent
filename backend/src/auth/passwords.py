"""Password resets without email: the app sends none (see `docs/password-reset/plan.md`).

- `reset(email)`: a new temporary password, for the owner to pass on (Admin tab), or for
  anyone from a shell: `python -m auth.access reset-password a@x.com`. That's also how the
  owner gets back in after forgetting their own password.
- `change(email, current, new)`: a signed-in user changes their own password.
"""

import secrets

from . import access, supabase
from .supabase import AuthError

MIN_LENGTH = 8


def _user_id(email: str) -> str:
    """The Supabase id for `email`: from the access list, else asked of Supabase."""
    entry = access.get(email)
    if entry is not None and entry.user_id:
        return entry.user_id
    found = supabase.admin_find_user(email)
    if found is None:
        raise AuthError(404, "There is no account with this email yet.")
    return found.id


def temporary_password() -> str:
    """12 URL-safe characters: easy to copy, ~72 bits of randomness."""
    return secrets.token_urlsafe(9)


def reset(email: str) -> str:
    """Give `email`'s account a new random password and return it."""
    password = temporary_password()
    supabase.admin_set_password(_user_id(email), password)
    return password


def change(user_id: str, email: str, current: str, new: str) -> None:
    """Change a signed-in user's password once their current one checks out."""
    if len(new) < MIN_LENGTH:
        raise AuthError(400, f"The new password needs at least {MIN_LENGTH} characters.")
    try:
        checked = supabase.password_login(email, current)
    except AuthError as exc:
        if exc.status == 401:
            raise AuthError(400, "Your current password is wrong.") from exc
        raise
    supabase.logout(checked.access_token)  # only needed to check the password
    supabase.admin_set_password(user_id, new)
