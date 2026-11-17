# Plan: port the frontend to the Map · Linen design

Source of truth: [`docs/ui_drafts_v2/04-map-linen/`](../../../docs/ui_drafts_v2/04-map-linen/README.md)
(`theme.css`, `shell.js`, `results.html`, `search.html`, `running.html`, `library.html`).

## Approach

The draft is a complete design system of its own (tokens in `:root[data-theme=light|dark]`,
component classes such as `.topbar`, `.co-panel`, `.pane`, `.row`, `.status`, `.drawer`).
Rebuilding it from BoardUI semantic tokens would lose the palette and type scale the owner
picked, so the app takes the draft's stylesheet directly:

- `src/styles/linen.css`: the draft's `theme.css`, ported almost verbatim (fonts switched to the
  self-hosted `@fontsource-variable/fraunces` and `@fontsource-variable/source-sans-3`).
- `src/components/icon.tsx`: the draft's SVG icon set as an `<Icon name="…" />` component, so
  icons match the mockups exactly.
- Tailwind / BoardUI styles are no longer loaded. BoardUI components the new pages no longer
  use are deleted; `frontend/AGENTS.md` is rewritten to describe the Linen rules instead.
- Theme: light by default, sun/moon toggle in the top bar, saved to `localStorage` (`na-theme`).
  A tiny inline script in `index.html` sets `data-theme` before first paint.

## Screens

| Draft | App | Notes |
|---|---|---|
| `shell.js` | `components/app-shell.tsx` (top bar, nav, theme toggle, user) and `search-history.tsx` (sidebar) | Sidebar becomes a drawer below 980px (menu button). Status dots: done / running / cancelled / failed. Delete asks to confirm; running searches get a stop button. |
| `search.html` | `pages/hero.tsx`, `search-boards.tsx`, `search-configs.tsx`, `saved-resume.tsx` | Form card + right rail ("Saved searches", "How results are organised"). Boards in a `<details>` with switches and max-jobs inputs. Inline rename stays (better than `prompt`). |
| `running.html` | `pages/running.tsx` | Orb, live status line, elapsed timer, Cancel (with confirm), 5 stages driven by the backend's progress messages, "Latest steps" log. Cancelled / failed searches show the error notice with "Edit and re-run" and "Retry search". |
| `results.html` | `pages/results.tsx` | Header (crumbs, title, location / time / boards), summary strip (stats, "Start here", one-line summary), sticky toolbar (Group by Company/Type, filter chips, sort), jump-to index, collapsible company panels with Jobs and People panes, cross-links, connect-message drawer, toasts with Undo for pins. |
| `library.html` | `pages/entities.tsx` | One header with count pill and sort, Companies / Jobs / People segmented tabs, row list with pins, status toggles, "How you align" / "Why connect" notes, the LinkedIn message, and "Last seen … in N searches" links. |

## Where the draft is mock-only

- **Tone (Warm / Short / Direct) and "About which role?" in the message drawer** rebuild the
  message client-side from canned text. The real message comes from the backend
  (`connect_message`), so the drawer shows that message in an editable box with a 300-character
  counter, Copy, Open LinkedIn and Mark connected. Tone and role are left out until the backend
  can generate variants.
- **"Found so far" partial results on the running page** need the backend to stream companies as
  they are found; today it sends one `result` event at the end, so this section is omitted.
- **Person → job link (`about`)**: results have no such field, so a job's cross-link offers the
  company's first contacts and a person's "Message" link opens the drawer without a role.
- **Fit score on library company rows**: entity records have no score, so it is not shown.

## Tests

Behaviour stays the same, so the existing tests are kept and updated for the new markup and
labels (e.g. `Mark applied` / `Applied` instead of `NOT APPLIED` / `APPLIED`, a native sort
`<select>`, panels that start collapsed except the top company). New tests cover the theme
toggle, results filters / grouping and the running-page cancel.
