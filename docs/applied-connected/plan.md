# Plan: APPLIED / CONNECTED toggles (keep a log of applications and connections)

TODO item: *"Every job that shows up for a user should have a toggle that says "APPLIED" or
"NOT APPLIED". And every person that shows up should have a toggle that says "CONNECTED" or
"NOT CONNECTED". That toggle is persisted across runs. So if the user applies to a job, does
another search, and the same job appears, it should stay as "APPLIED"."*

## The hard part: stable identity across searches

Each search is a fresh LLM run, so the same job/person comes back as a new object. A status
therefore has to be keyed by a deterministic **entity key** derived from the entity itself,
not by search id or list position. All key logic lives in `backend/src/entities/keys.py`
(pure functions, no storage) so the upcoming Companies/Jobs/People pages can reuse it to
de-duplicate everything seen across searches.

Key format: `<kind>:<scheme>:<value>` (e.g. `job:url:linkedin.com/jobs/view/3812345678`).

### URL normalization (`normalize_url`)

- Only `http(s)` URLs with a host count; anything else gives no URL key (→ fallback).
- Scheme is dropped (http == https); host is lower-cased with `www.` / `m.` removed; default
  ports dropped; fragment dropped; duplicate/trailing slashes collapsed.
- Tracking parameters are removed (`utm_*`, `gclid`, `fbclid`, `trk`, `trackingId`, `refId`,
  `ref`, `src`, `source`, `lipi`, `gh_src`, `lever-*`, ...). Remaining params are sorted.
- LinkedIn (`*.linkedin.com`, incl. country subdomains like `uk.`): all query params dropped,
  path lower-cased. Job URLs collapse to `linkedin.com/jobs/view/<numeric id>` (from
  `/jobs/view/<slug>-<id>` or `?currentJobId=<id>`).
- Indeed: only the posting id (`jk` / `vjk`) is kept, as `indeed.com/viewjob?jk=<id>`.

### Keys per entity

| Entity  | Primary key                                   | Fallback (no usable URL)                 |
|---------|-----------------------------------------------|------------------------------------------|
| Job     | `job:url:<normalized posting url>`            | `job:name:<company>\|<title>`             |
| Person  | `person:linkedin:<profile slug>` (`/in/<slug>`) or `person:url:<normalized url>` | `person:name:<name>\|<company>` |
| Company | `company:name:<company name>` (helper only; for the next task) | –                       |

Names are normalized with Unicode NFKD (accents stripped), case-folded, punctuation turned
into spaces and whitespace collapsed; company names also lose legal suffixes (`Inc`, `LLC`,
`Ltd`, `Corp`, `Co`, ...). Companies are keyed by name rather than URL because the agent
links a company sometimes to LinkedIn and sometimes to its website, while the name is stable.

Trade-off: a job reposted under a new URL, or a person returned once with and once without a
profile URL, gets a different key. Preferring the URL avoids false merges (two different
"Data Analyst" postings at one company), which would be worse for an application log.

## Where keys come from

`JobResult` and `PersonResult` gain a server-filled `key: str` field. It is marked
`SkipJsonSchema`, so the LLM's structured-output schema is unchanged; the server calls
`entities.keys.annotate(results)` before streaming the `result` event and again when a saved
search is reopened (so older saved searches, and future changes to normalization, are always
keyed with the current rules). The frontend never computes keys.

## Storage

- `database/users/<user_id>/statuses.json`:
  `{"job": {"<key>": {"active": true, "updated_at": "..."}}, "person": {...}}`.
  Un-toggling keeps the entry with `active: false` (a tiny audit trail).
- `backend/src/userdata/statuses.py`; functions take an explicit `user_id` like history, are
  guarded by a process-wide lock and write atomically (tmp file + replace).
- Housekeeping: `accounts.py` and `history.py` move into the new `backend/src/userdata/`
  package (everything that reads/writes per-user data, i.e. what moves to Supabase later).

## API

- `GET /api/statuses` → `{"job": {"<key>": true|false}, "person": {...}}` for the current user.
- `PUT /api/statuses` with `{"kind": "job"|"person", "key": "...", "active": bool}` →
  the stored entry. Idempotent "set" (not "flip") so optimistic UI updates can't drift.
  Keys are validated (prefix must match the kind, max 1000 chars).

## Frontend

- `api.ts`: `key` on `JobResult`/`PersonResult`, `getStatuses()` / `setStatus()`.
- New `components/status-toggle.tsx`: a React Aria `ToggleButton` styled like the BoardUI
  `Chip` (lime when on, neutral when off, check icon), labels exactly `APPLIED` /
  `NOT APPLIED` and `CONNECTED` / `NOT CONNECTED`.
- `App.tsx` loads the status map on mount and owns it; toggles update it optimistically and
  roll back (with an inline error) if the request fails. `Results` shows a toggle on every
  job and person row — live results and reopened searches alike, since both are keyed.

## Verification

- pytest: key normalization (tracking params, LinkedIn slugs/job ids, fallbacks), status
  persistence, endpoints, and the "applied job in search 1 shows APPLIED in search 2" flow
  through `TestClient` with a mocked agent; LLM schema unchanged. ruff check/format.
- `npm run build` and `npm run lint` in `frontend/`.
