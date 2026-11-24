# Related entities under entity cards

TODO: redirects to related entities from entity cards.

## How entities relate in the saved data

A saved search holds `companies[]`; each company has its own `jobs[]` and `people[]`. There is
no direct person-to-job link (people are found per company, or per company and job on demand,
but the person record does not store which job). So the only relation is **company**:

- company -> jobs and people at that company
- job -> people at the same company (people to connect with)
- person -> jobs at the same company

The catalog (`backend/src/entities/catalog.py`) already stamps every job and person entity with
`company_key` (the stable `company:name:...` key), and the company entity's `key` is the same
string. So no backend change is needed.

## Approach (frontend only)

- Each page also loads the other lists it needs (`useEntities`), groups them by `company_key`
  (`utils/related.ts`) and passes the matches to the row.
- `Related` renders a labelled list of pill buttons (job / person colours) under the card,
  and nothing when empty.
- Click: `App` stores a `focus` ({kind, key}) and switches the hash to that page. The page
  scrolls to `#entity-<key>` and highlights the card for 2.5s (`.row.focused`), then the app
  clears the focus. Cards are only sorted, never filtered, so the target is always present.
- If the extra list fails to load the section is just hidden.

## Tests

`utils/related.test.ts` and `pages/entities-related.test.tsx` (mocked fetch).
