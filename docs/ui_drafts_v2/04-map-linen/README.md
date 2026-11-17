# v2 #4: Map · Linen

Open `results.html` (centrepiece), `search.html`, `running.html`, `library.html`. Light by default; the sun/moon toggle in the top bar saves to `localStorage` (`na-theme`).

## What changed from v1 Company Map, and why
| Owner feedback | Change |
|---|---|
| Likes the results page | Kept: collapsible company panels, jobs and people side by side, sticky jump-to index, Group by Company/Type, filter chips, sort, cross-links, connect-message drawer, pins, Applied/Connected toggles, copy feedback. |
| Likes Field Notes colours, not its format | Full Linen re-theme (cream, terracotta, violet/teal/amber). Fraunces is used only for modest headings (24px h1); no editorial layout, no "Start here" card band, no right rail. |
| Wants light default plus toggle | Light default; dark mode is neutral black with a light-blue accent family (revised per owner: no dark reds/oranges). Same tokens swapped via `html[data-theme]`. |
| v1 flaw: ~480px header above first company | Header is now title/meta row, one summary strip (inline stats, one-line summary with "Read full summary", compact "Start here" link) and the sticky toolbar. First panel starts at y=380 at 1440x900 and its body is open above the fold (v1: ~860). |
| Inactive toggles must pass AA | Chips, segmented buttons and status toggles use text2/text on solid tokens; checked in both themes. |

## Palette (light / dark)
Light mode is deliberately restrained (owner feedback: too many colours): warm neutrals, terracotta for actions/companies/pins, one teal for positive states (applied, connected, strong fit), and red only for errors. Jobs and people are told apart by icon and label, not colour.

bg `#FAF6F0` / `#0A0A0B`; surface `#FFFFFF` / `#141416`; alt `#F2EBE0` / `#1E1F23`; border `#E4D9C8` / `#2E3036`; input outline `#8F7B63` / `#6B7280`; text `#2B2420` / `#F2F4F7`; text2 `#6B5E54` / `#A8B0BD`; accent `#C2410C` / `#7DC4FF` (hover `#9A3412` / `#A8D8FF`, on-accent `#FFFFFF` / `#04121F`); company `#C2410C` / `#A5B8FF`; job `#6B5E54` / `#7DD3FC`; person `#6B5E54` / `#8BE3F0`; pinned `#C2410C` / `#BFE3FF`; applied `#0F766E` / `#86E1D5`; connected `#0F766E` / `#9CC8FF`; danger `#B91C1C` / `#FCA5A5` (dark mode's only warm colour, kept for failed/delete states). Each entity also has `-d` (text on tint) and `-t` (tint) steps.
Accent vs person: both warm, so person is always paired with a round avatar or users icon and an amber tint; accent is used for actions and links only.

## Type scale
Fraunces (headings) and Source Sans 3 (UI/body). Body 16; meta 14 to 13.5; h1 24; company name 20; row title 15.5; fit score 22; stat numbers 20; chips 13.5.

## Implementation notes (`theme.css`)
- Tokens live in `:root[data-theme=light|dark]`; components only use `var(--token)`, no hex. A tiny head script sets the theme before paint.
- Components: `.topbar`, `.side`, `.strip` (stats + summary), `.toolbar` (sticky), `.index`, `.co-panel`, `.pane.jobs/.people`, `.row`, `.pill.*`, `.status.app/.con`, `.drawer`, `.toast`, `.theme-tog`.
- `shell.js` injects the icon sprite, nav, sidebar and theme toggle; `data.js` holds the sample data.
- Breakpoints: 1180 (index becomes chips), 980 (sidebar drawer), 720 (compact).

## Verification
Playwright: no console errors and no horizontal scroll at 1440 and 390 in both themes; text contrast audit over results (collapsed, expanded, type view, drawer), search, running, library in both themes: all text meets AA (4.5:1, 3:1 large). Fixed during the audit: accent text on tints now uses the darker accent.
