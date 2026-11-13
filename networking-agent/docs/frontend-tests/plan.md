# Plan: Frontend test runner + pinned-behaviour tests

Request: *"add a test runner for the frontend to make sure that frontend tests are all
confidently confirmed, then test the Pinned behavior."*

## Runner

- **Vitest** (shares the Vite config, so the `@/` alias and the React plugin just work),
  **jsdom** as the DOM, **@testing-library/react** + **user-event** + **jest-dom** matchers.
- Config lives in a `test` block in `frontend/vite.config.ts`
  (`/// <reference types="vitest/config" />` for the types):
  `environment: 'jsdom'`, `setupFiles: ['./src/test/setup.ts']`,
  `include: ['src/**/*.test.{ts,tsx}']`, `restoreMocks` / `unstubGlobals` so spies and
  `vi.stubGlobal('fetch', ...)` reset between tests.
- No `globals: true`: tests import `describe` / `it` / `expect` / `vi` from `vitest`
  explicitly, and `src/test/setup.ts` registers RTL's `cleanup` and the jest-dom matchers
  (`@testing-library/jest-dom/vitest`, which also adds their types).
- Test files live next to the code (`*.test.ts(x)`) under `src`, so `tsc -b` type-checks
  them as part of `npm run build`; Vite never bundles them (nothing imports them).
- Shared builders for entities / empty maps: `src/test/fixtures.ts`.

## Running

```sh
cd networking-agent/frontend
npm run test        # one-off run (CI / before committing)
npm run test:watch  # re-run on save
npx vitest run src/pages/entities.test.tsx   # a single file
```

## Coverage

| File | What it checks |
| --- | --- |
| `utils/sort-entities.test.ts` | Every sort option on companies / jobs / people; "Pinned first" per kind, only reading that kind's pin slice; `pinned: false` / missing pins = unpinned; ties keep the incoming (recency) order; unknown sort id falls back to "Most recent"; input not mutated; unique option ids and option order. |
| `utils/count-status.test.ts` | X/Y counts: missing / false = off, unlisted keys ignored, empty list. |
| `utils/use-keyed-toggles.test.ts` | Optimistic toggle before the save resolves; only the toggled key changes; rollback + error message on a failed save; later success clears the error; a stale failure never rolls back a newer change. |
| `components/pin-toggle.test.tsx` | "Pin <name>" accessible name (and the "Pin for later" fallback), `aria-pressed`, outline vs filled icon and styling, click / keyboard calls `onChange` with the next state, controlled behaviour. |
| `pages/entities.test.tsx` | Renders the full `App` at `#/companies`, `#/jobs`, `#/people` against a stubbed `fetch` backend: saved pins load from `GET /api/pins`; clicking a card's pin flips it and sends `PUT /api/pins` with `{kind, key, pinned}`; "Pinned first" puts pinned cards first (and re-sorts live when you pin); a failed PUT rolls the pin back, shows the error banner, and keeps the card in place. |

## Verification

`npm run test`, `npm run build`, `npm run lint` in `frontend/`. The tests were also checked
against deliberate regressions (removing the rollback in `useKeyedToggles`, swapping the
companies "Pinned first" comparator) to make sure they fail when the behaviour breaks.
