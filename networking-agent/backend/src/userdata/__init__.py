"""Per-user data stored in the local `database/` folder (POC stand-in for Supabase).

- `accounts`: users and the per-user folder (`database/users/<user_id>/`).
- `history`: saved searches.
- `statuses`: APPLIED / CONNECTED toggles, keyed by `entities.keys`.
- `pins`: pinned companies / jobs / people, keyed by `entities.keys`.
- `storage`: JSON read / atomic-write helpers shared by the stores above.

Everything that reads or writes user data lives here, so the Supabase migration only
touches this package.
"""
