# v2 #1: Command · Linen

Three-pane Command Center (Previous Searches sidebar, tabbed/filterable/sortable list with Compact/Comfortable density, detail pane, j/k/p/a/c/o/d/1-3// shortcuts, Ctrl+K palette) restyled in the Linen palette. Open `results.html` (centrepiece), `search.html`, `running.html`, `library.html`.

## What changed from v1, mapped to the feedback
| Feedback | Change |
|---|---|
| Keep Command Center structure | Layout, data, keyboard and palette code carried over unchanged. |
| "Not dark by default" | Light (Linen) is the default. A Light/Dark toggle in the top bar (also in Ctrl+K) saves to `localStorage` key `cl-theme`. |
| Dark mode | "Espresso": warm brown-tinted dark (#1D1612 base), not grey-black. |
| Liked Field Notes colours | Cream surfaces, terracotta accent, violet (companies), teal (jobs), amber-brown (people). |
| v1 flaw: toggle label failed AA | Root cause: the toggle buttons carried `data-theme="dark"`, so they re-scoped the theme tokens on themselves. Renamed to `data-set`. Active option is now filled terracotta. |
| v1 flaw: empty detail pane | Detail opens on the top company (and top job/person per tab). On mobile it is a slide-up sheet. |

Also: Fraunces (serif) only for the search title, detail title and search hero; Source Sans 3 everywhere else. Gradients removed; accent text uses a darker `--accent-ink`.

## Palette
| Token | Light (Linen) | Dark (Espresso) |
|---|---|---|
| bg / surface / surface-alt | #FAF6F0 / #FFFFFF / #F2EBE0 | #1D1612 / #281E18 / #352A22 |
| border / input-border | #E4D9C8 / #8F7C65 | #4A3A2F / #9A8573 |
| text / text-2 | #2B2420 / #645850 | #F6EDE3 / #C7B8A8 |
| accent / hover / ink / on-accent | #C2410C / #9A3412 / #9A3412 / #FFFFFF | #F08A5D / #F6A57F / #F6A57F / #2A1206 |
| company / job / person | #6D28D9 / #0F766E / #92400E | #C9B8FF / #5FD6C4 / #F4B863 |
| pinned / applied / connected | #854D0E / #166534 / #1E40AF | #F2C14E / #86D99F / #A3BCFF |
| danger | #B91C1C | #FCA5A5 |

## Type scale
Body 14.5px; meta 12-13px; row title 14px (13 compact); tab 14px; panel heading 15px; section heading 17px; stat numbers 20px; detail title 26px Fraunces 600; page title 23px Fraunces 600 (19px mobile); hero 38px (30 mobile).

## Implementation notes
- `theme.css` is token-first: the two `[data-theme]` blocks at the top are the only place colours live. Entity/status colours are applied by setting `--c` (`.c-company`, `.s-pinned`, ...) and components (`.pill`, `.chip-icon`, `.avatar`, `.btn.on`, `.tab .i`) derive text and tint from it with `color-mix`, so new entity types need one token.
- Theme is applied before paint by an inline script in each page's head; `shell.js` owns the toggle.
- Components: `.btn`, `.pill`, `.fchip`, `.seg`, `.row` (+ `.meter`), `.panel`, `.acc`, `.palette`, `.toast`.
- Checks (Chromium via Playwright): no console errors, no horizontal scroll at 1440 and 390; zero text-contrast failures (4.5:1, 3:1 for large) on all four pages in both themes, plus after interactions (selection, people tab, copy, applied, pin filter, compact, palette, toast).
