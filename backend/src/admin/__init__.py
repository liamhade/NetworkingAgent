"""The owner's Admin tab: every user's email, access status and LLM usage, and the whitelist.

The whitelist is the `approved` entries of `auth.access`; `overview` merges it with the user
folders and `llm_usage.csv`. Only `OWNER_EMAIL` may use it (`auth.session.require_admin`).
Plan: `docs/admin/plan.md`.
"""
