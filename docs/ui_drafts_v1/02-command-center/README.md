# Direction 2: Command Center (Midnight dark, Harbor light)

Open `results.html` (centrepiece). Also: `search.html`, `running.html` (live progress, cancel, streaming results), `library.html?t=companies|jobs|people`. Shared files: `styles.css` (all tokens), `shell.js` (top bar, Previous Searches, Ctrl/Cmd+K palette, theme), `data.js`, `results.js`. No build step; `preview.png` is a 1440px capture.

## Problems fixed (audit refs)
- **P0 dull/flat**: real colour system. Neutrals tinted blue-black (not grey), one mint (dark) / blue (light) action colour, one hue per entity (company violet, job sky, person amber), green only for Applied, blue only for Connected, amber for pins. Fit is a meter plus a ring, not a grey chip. Wordmark and brand mark added.
- **P0 overload**: nothing nests three deep. The list shows one 2-line row per item (name, facts, first sentence of the alignment note). Full note, jobs, people and the connect message live in the right pane, and only for the selected item. Inside it: accordions, top 3 people then "Show all". Compact/Comfortable density toggle.
- **P1 hierarchy**: 21px search title, 24px detail title, 17px section heads, 14px row titles, 12.5px meta. Stats strip (counts, applied/connected progress). Job score now visible.
- **P1 navigation**: Companies/Jobs/People tabs with counts, filter chips, sort, text filter, group-by-company, j/k, command palette, cross-links (job to company, person to company, "Also at...").
- **Affordances**: "Mark applied/connected" are labelled buttons that become coloured pills with a check; labelled pins with Undo toast; Copy gives "Copied" feedback; Find People shows a time hint and loading state; Cancel is in the running page and sidebar.
- **Mobile**: sidebar becomes a drawer, detail becomes a full-screen sheet with Back.

## Palette
Midnight: bg #0E1116, surface #161B22, alt #1E252E, border #2A323D, text #E8ECF1, text-2 #9AA7B6, accent #5EEAD4 (on-accent #04201C), company #C4B5FD, job #7DD3FC, person #FCD34D, pinned #FBBF24, applied #86EFAC, connected #93C5FD.
Harbor: bg #F4F7FB, surface #FFFFFF, alt #E8EEF6, border #D5DEEA, text #0F1E33, text-2 #516179, accent #1D4ED8, company #6D28D9, job #0369A1, person #0F766E, pinned #B45309, applied #15803D, connected #4338CA. Pill text is darkened by `color-mix` in light mode for AA. Status always pairs colour with an icon and label.

## Type
Space Grotesk (headings, numerals) and IBM Plex Sans (body), tabular numbers for scores and counts. Scale: 36 hero, 24 detail title, 21 page title, 17 section, 14 row title / body, 13 to 12.5 meta, 12 to 11 caps labels. Nothing under 11px; body in the detail pane is 14.5px at 68ch.

## IA
Sidebar (history with running dot, Cancel, Delete-confirm) | list pane (tabs, filters, rows) | detail pane. Top nav keeps Search/Companies/Jobs/People; the three entity links lead to library tables (all searches).

## Porting to the real code
- Replace `theme.css` accent ramp and add semantic tokens: `--color-company/job/person/pinned/applied/connected`, plus a `[data-theme=light]` block (the existing `.dark` block can host Midnight). Raise tertiary text to `text-2` (fixes the 2.6:1 failure).
- New components: `SplitView`, `ListRow` (company/job/person), `DetailPane`, `FilterChip`, `Tabs`, `Segmented`, `CommandPalette`, `StatsStrip`, `Stepper`/progress bar. Reuse Accordion, Switch, NumberField, Input, Textarea, FileUpload.
- Rework `results.tsx` (CompanyCard becomes row + detail), `top-nav.tsx` (brand, theme toggle), `search-history.tsx` (running group, drawer under md).
- Future backend work (mocked here): per-step progress events and partial results, regenerate message, filters/sort server-side.

## Compromises
Data is static; Find People adds three invented people; the palette is non-persistent beyond localStorage; library pages are a simple table.
