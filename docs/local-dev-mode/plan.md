# Plan: LOCAL_DEV_MODE (sign in as TEST_USER with any credentials)

## Ask

A mode to toggle on and off that keeps the sign-in page but drops the password: clicking
**Sign in**, whatever was typed, signs in as TEST_USER.

## Toggle

`LOCAL_DEV_MODE=true` in `.env` (restart the backend to switch). Off by default. When on it
takes precedence over the Supabase settings: no Supabase call is made for sign-in, and the
backend logs a warning at startup.

## Behaviour

- `/api/auth/config` answers `enabled: true, local_dev: true`, so the page shows the sign-in
  form, with a note that any email and password work (empty ones too).
- `/api/auth/login` (and `/api/auth/signup`) ignore the body, set an HttpOnly `na_dev` cookie
  and return TEST_USER.
- `SessionMiddleware`: with the cookie, every `/api` request is TEST_USER; without it, 401, so
  the sign-in page comes back after **Sign out** (which clears the cookie).
- TEST_USER is the admin in this mode (Admin tab visible). The whitelist still edits the local
  `access.json`. Password endpoints (change, owner reset) answer 404: there's no password.
  The **Change password** button is hidden.

## Safety

The mode must never let anyone in on a deployed server. Dev sign-in (and the dev cookie) only
count for requests from a loopback address (`127.0.0.1`, `::1`) with no `X-Forwarded-For`
header, which a hosting proxy (Railway) always adds. A deployed server with the flag on
by mistake just refuses every sign-in (403). Consequence: inside Docker on your own machine
(requests come from the Docker bridge, not loopback) dev mode refuses too; run the backend
directly (`uvicorn`, with Vite's proxy) to use it.
