# Plan: Pin entities for later

TODO item: *"(pin for later) We should be able to pin entities to come back to for later if
we're interested in them. We can then pull up our pinned entities in their individual pages
by sorting by pins."*

Pins follow the APPLIED / CONNECTED pattern (`docs/applied-connected/plan.md`): persisted
per user, keyed by the stable entity keys from `entities.keys`, toggled optimistically in the
UI with rollback on failure. Unlike statuses, pins apply to all three kinds, companies
included.

## Backend

### Company keys in search results

Jobs and people already carry a server-filled `key`; companies did not (the catalog computed
`company_key` itself). `CompanyResult` gains the same hidden `key: SkipJsonSchema[str]`
field, and `entities.keys.annotate` fills it with `company_key(name)`, so a company can be
pinned from the search results page and the pin matches the Companies page. The LLM's
structured-output schema is unchanged (existing test asserts `"key"` never appears).

### Storage

- `database/users/<user_id>/pins.json`:
  `{"company": {"<key>": {"pinned": true, "updated_at": "..."}}, "job": {...}, "person": {...}}`.
  Unpinning keeps the entry with `pinned: false`, like statuses.
- New module `backend/src/userdata/pins.py` (same lock + atomic tmp-file-replace write and
  "corrupt file reads as empty" behaviour as `statuses.py`). The JSON read / atomic write
  helpers are pulled into `userdata/storage.py` and shared by both modules.

### Schemas

- `PinKind = Literal["company", "job", "person"]`
- `PinUpdate {kind, key (1..1000 chars), pinned: bool}`; `EntityPin(PinUpdate) {updated_at}`.

### API

- `GET /api/pins` → `{"company": {"<key>": true|false}, "job": {...}, "person": {...}}`.
- `PUT /api/pins` with `{"kind", "key", "pinned"}` → stored entry. Idempotent set, not
  flip. 422 if the key prefix does not match the kind.

## Frontend

- `api.ts`: `key` on `CompanyResult`; `PinKind`, `PinMap`, `getPins()`, `setPin()`.
- `components/pin-toggle.tsx`: icon-only React Aria `ToggleButton` (remixicon
  `RiPushpinLine` / `RiPushpinFill`), accessible name "Pin <name>" + `aria-pressed`.
  Pinned uses the ghost-button accent tokens; unpinned is a quiet tertiary icon.
- `utils/use-keyed-toggles.ts`: the optimistic set-with-rollback logic from `App.tsx`
  (per-entry version counter so a stale failure can't undo a newer change), now shared by
  statuses and pins.
- `App.tsx` loads pins alongside statuses (with retry) and passes `pins` / `pinError` /
  `onTogglePin` to the Companies / Jobs / People pages and to `Results`.
- Pin toggle on every company, job and person card on the entity pages, and on company
  cards and job / person rows in search results (rows without a key show no toggle).
- Sorting: `SortContext` gains `pins: PinMap`; new `byPinned(kind)` comparator and a
  "Pinned first" option (second, after "Most recent") on all three pages. Sorting is stable,
  so pinned and unpinned groups each keep the server's recency order.

## Verification

- pytest: pin round trip / per-user scoping / unpin keeps entry / corrupt file / wrong-kind
  key; endpoints (GET/PUT, validation); company key present in streamed and reopened results
  and stable across searches; pins and statuses don't clobber each other.
- `ruff check .`, `ruff format --check .`, `npm run build`, `npm run lint`.
