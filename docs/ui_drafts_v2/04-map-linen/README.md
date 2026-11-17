# v2 #4: Map · Linen

Open `results.html` (centrepiece), `search.html`, `running.html`, `library.html`. Light by default; the sun/moon toggle in the top bar saves to `localStorage` (`na-theme`).

## What changed from v1 Company Map, and why
| Owner feedback | Change |
|---|---|
| Likes the results page | Kept: collapsible company panels, jobs and people side by side, sticky jump-to index, Group by Company/Type, filter chips, sort, cross-links, connect-message drawer, pins, Applied/Connected toggles, copy feedback. |
| Likes Field Notes colours, not its format | Full Linen re-theme (cream, terracotta, violet/teal/amber). Fraunces is used only for modest headings (24px h1); no editorial layout, no "Start here" card band, no right rail. |
| Wants light default plus toggle | Light default, warm espresso dark (not grey-black), same tokens swapped via `html[data-theme]`. |
| v1 flaw: ~480px header above first company | Header is now title/meta row, one summary strip (inline stats, one-line summary with "Read full summary", compact "Start here" link) and the sticky toolbar. First panel starts at y=380 at 1440x900 and its body is open above the fold (v1: ~860). |
| Inactive toggles must pass AA | Chips, segmented buttons and status toggles use text2/text on solid tokens; checked in both themes. |

## Palette (light / dark)
bg `#FAF6F0` / `#1B1512`; surface `#FFFFFF` / `#261E19`; alt `#F2EBE0` / `#352A22`; border `#E4D9C8` / `#4A3C31`; input outline `#8F7B63` / `#9A8674`; text `#2B2420` / `#F4ECE2`; text2 `#6B5E54` / `#C0B1A1`; accent `#C2410C` / `#F08A5D` (hover `#9A3412` / `#F7A482`, on-accent `#FFFFFF` / `#2A140A`); company `#7C3AED` / `#B89CF8`; job `#0F766E` / `#4FCBBA`; person `#B45309` / `#F2B04C`; pinned `#A16207` / `#E9D26A`; applied `#15803D` / `#6FD08A`; connected `#1D4ED8` / `#8FB1FF`; danger `#B91C1C` / `#FF9087`. Each entity also has `-d` (text on tint) and `-t` (tint) steps.
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
