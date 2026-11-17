# v2 #2: Command · Harbor

Command Center's three-pane workspace (Previous Searches sidebar, tabbed list, detail pane) in the Harbor palette, light by default. Open `results.html` first; `search.html`, `running.html` and `library.html` share the same shell. Previews: `preview.png` (light) and `preview-dark.png` (dark), both 1440x900.

## What changed from v1, mapped to the owner's feedback

| Feedback | Change |
|---|---|
| Keep Command Center's structure | Same three panes, tabs, filter chips, sort, compact/comfortable density, `j/k/p/a/c/o/d/1-3//` keys and Ctrl+K palette. |
| Dislike the dark default; want light plus a toggle | Light is the default. Light/Dark segmented toggle in the top bar (also `t` and the palette), saved in `localStorage` (`cch-theme`). Dark is a navy tint (`#0B1527`), not grey-black. |
| Like Company Map's colours | Harbor values copied exactly: `#1D4ED8` accent, violet companies, sky jobs, teal people, amber pins. |
| (Flaw) inactive toggle label failed AA | The cause was `[data-theme]` also matching the toggle buttons, so they picked up the other theme's tokens. Theme tokens are now scoped to `html[data-theme]`, and the inactive label is `--text2` on `--alt`. |
| (Flaw) empty first screen | Detail pane opens on the top company (Tracksuit) with its first job and first person expanded. |
| Company Map touches | Fit bars with "Strong / Good / Possible fit" labels; coloured stat cards (left border plus tinted numerals); "Message X about Y" cross-links in job rows, job detail and person detail. |

## Palette

| Token | Light | Dark |
|---|---|---|
| bg / surface / alt | `#F4F7FB` / `#FFFFFF` / `#E8EEF6` | `#0B1527` / `#112038` / `#1B2D4B` |
| border / input border | `#D5DEEA` / `#7A8CA6` | `#2A3E60` / `#6B80A3` |
| text / text2 | `#0F1E33` / `#516179` | `#E6EDF8` / `#A3B3CE` |
| accent / accent-text / on-accent | `#1D4ED8` / `#1E40AF` / `#FFFFFF` | `#5B8DFF` / `#9DBBFF` / `#07122A` |
| company fill / text / tint | `#6D28D9` / `#5B21B6` / `#F1EBFD` | `#A98BFF` / `#CDBBFF` / `#2A2253` |
| job | `#0369A1` / `#075985` / `#E2F1FA` | `#4BB8F0` / `#8CD3F6` / `#10304B` |
| person | `#0F766E` / `#115E59` / `#DDF3F0` | `#35C9B8` / `#6FDDD0` / `#0E3A3E` |
| pinned | `#B45309` / `#92400E` / `#FDF1DC` | `#F2B14A` / `#F8C97D` / `#3A2D14` |
| applied | `#15803D` / `#166534` / `#E1F5E7` | `#4ADE80` / `#8BEFAE` / `#12392B` |
| connected | `#4338CA` / `#3730A3` / `#E8E7FB` | `#9A9DFF` / `#C0C2FF` / `#272B5E` |

## Type scale

Manrope (headings) and Public Sans (body), via Google Fonts with system fallbacks. 11 caps labels, 12 meta, 13 UI, 14 body, 14.5 detail prose, 16-17 section heads, 20 page title, 25 detail title, 34 hero, 36 big fit score.

## Implementation notes

- `theme.css` is the only stylesheet. Tokens live on `:root, html[data-theme="light"]` and `html[data-theme="dark"]`; components never use raw hex.
- Each entity or status gets three tokens through a hook class (`.c-company`, `.c-job`, `.c-person`, `.s-pinned`, `.s-applied`, `.s-connected`): `--c` for fills and strokes, `--cd` for text on surface or tint, `--ct` for tint backgrounds. Pills, icon chips, stat cards and the active `.btn.on` state all use these, so a new entity type is three variables.
- Fit component: `.fit.strong|good|fair` sets `--fc` (bar) and `--fd` (text); `.fit.lg` is the detail-pane version.
- Prototype only: `data.js` (sample data plus an `about` map from person to job), `shell.js` (top bar, sidebar, palette, theme), `results.js` (list and detail logic).
- Verified with Playwright: no console errors and no horizontal scroll at 1440 and 390 in both themes; a computed-style text-contrast check (4.5:1, 3:1 for large text) on results, search, running, library, the palette and the jobs and people tabs found no failures in either theme.
