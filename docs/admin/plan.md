# Plan: owner-only Admin tab (whitelist + LLM usage)

## Ask

Only people the owner allows may use the app. An **Admin** tab, shown only to the owner
(`OWNER_EMAIL`), lists every user's email and LLM usage and lets the owner add emails to, or
remove them from, the whitelist. An email that isn't on the whitelist can't use the app.

## Whitelist = the existing access list

`<DATABASE_DIR>/access.json` (`auth.access`) already gates every `/api` request: only entries
with status `approved` get through (`SessionMiddleware`, `/api/auth/login`). So the whitelist
is the set of `approved` emails, and no second list is added:

| Admin action          | `access.json`                                    |
|-----------------------|--------------------------------------------------|
| Add email             | `approve` (also pre-approves an email that hasn't asked yet) |
| Approve a request     | `approve`                                        |
| Remove / deny         | `deny`: blocked at once, also for live sessions  |

Remove sets `denied` instead of deleting the entry, because a missing entry would re-approve an
old invite-code account (the legacy migration in `access.status_of`) and would let the person
request access again as if new.

## Owner

- `OWNER_EMAIL` (env, compared lower-cased) is always allowed in. Its sign-up is approved at once
  and it can't be removed or denied (the API answers 400).
- `/api/me` gains `is_admin`. With accounts on, it's true only for the owner. Without accounts
  (local development, everyone is TEST_USER) it's true, so the page can be tried locally. That
  is safe because a server without accounts is open to everyone anyway and must never be deployed.

## API (owner only, 403 for anyone else)

- `GET /api/admin/users`: one row per known email, merged from the access list and the user
  folders: email, access status, user id, requested/decided/joined dates, plus LLM calls,
  tokens, cost and last use from `llm_usage.csv` (summed per `user_id`). Usage rows for ids
  with no known email (e.g. TEST_USER) are listed by id. Also the overall totals and the owner email.
- `PUT /api/admin/whitelist` `{email}`: approve.
- `DELETE /api/admin/whitelist/{email}`: deny.

Logic lives in `backend/src/admin/` (service-oriented); `server.py` only routes.

## UI

`#/admin`, a nav item with a shield icon that only shows when `is_admin`. It contains:
- An "Add to whitelist" email form.
- A users table: email (owner marked), status pill, LLM calls / tokens / cost, last used, joined,
  and actions: **Approve** (pending/denied), **Remove** (approved), **Deny** (pending).
- Totals in the header.

## Not done

No per-day usage charts, and no audit log of who changed the list (there's only one admin).
