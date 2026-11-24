"""Accounts: Supabase email + password sign-in, gated by invite codes.

On only when `config.auth_enabled()` (Supabase URL and keys set); otherwise every request is
TEST_USER. Plan: `networking-agent/docs/deploy/plan.md` (Phase 2).

- `supabase`: Supabase Auth REST calls (`AuthError`, `Session`, `SupabaseUser`).
- `invites`: invite codes in the local database folder, plus the `python -m auth.invites` CLI.
- `session`: HttpOnly session cookies, `SessionMiddleware`, and the `current_user` dependency.
"""
