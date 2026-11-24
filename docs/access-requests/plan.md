# Plan: access requests by email (replaces invite codes)

## Ask

Instead of invite codes, people send the owner an email so the owner can confirm the address
is theirs, then let them in.

## Flow

1. On the sign-in page, **Request access**: email + password (8+ characters).
2. The server creates the Supabase account (confirmed, so no Supabase email setup) and records
   the email as `pending` in `<DATABASE_DIR>/access.json`. No session is issued.
3. The page shows a **Send the request email** button: a `mailto:` to `ACCESS_REQUEST_EMAIL`
   with the subject and body filled in. Sending it from that address is the proof that the
   person owns it.
4. The owner checks that the email came from the address in the body and approves:
   `python -m auth.access approve a@x.com` (on Railway: `railway ssh -- python -m auth.access ...`).
5. The person signs in with the password they chose. Until then, sign-in answers 403 "waiting for
   approval" and shows the email button again.

`approve` also works for an email that hasn't asked yet (pre-approval): its request is approved
at once and signs straight in. `deny` blocks an email (pending or approved, effective on the
next request). `list` shows everything, pending first.

## Enforcement

- `/api/auth/login` checks access after the password; a non-approved user gets 403 and the
  fresh Supabase session is revoked.
- `SessionMiddleware` checks access on every `/api` request, uncached, so `deny` takes effect
  at once and a token obtained straight from Supabase (anon key) still can't use the app.
- Emails are compared lower-cased and trimmed.

## Migration

Accounts made with invite codes are in `invite_codes.json` (`used_by` = Supabase user ids). The
first time such a user is seen, they are written to `access.json` as approved, so existing
testers keep working. `auth/invites.py` and the invite-code UI are removed.

## Config

`ACCESS_REQUEST_EMAIL`: the owner's inbox. `/api/auth/config` returns it as `request_email`
(it has to be public for the button to work). Unset: the page asks people to contact the
owner, without a button.

## Not done

The server sends no email itself (would need an email provider). Approval is a CLI command,
not a web page.
