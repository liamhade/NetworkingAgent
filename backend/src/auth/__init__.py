"""Accounts: Supabase email + password sign-in, for emails the owner approved.

On only when `config.auth_enabled()` (Supabase URL and keys set); otherwise every request is
TEST_USER. Plans: `docs/deploy/plan.md` (Phase 2), `docs/access-requests/plan.md`.

- `supabase`: Supabase Auth REST calls (`AuthError`, `Session`, `SupabaseUser`).
- `access`: access requests and approvals in the local database folder, plus the
  `python -m auth.access` CLI.
- `session`: HttpOnly session cookies, `SessionMiddleware`, and the `current_user` dependency.
"""
