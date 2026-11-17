# v2 #5 Command · Tree

Open `results.html` (centrepiece), `search.html`, `running.html`, `library.html`. Static, double-click to open. Previews: `preview.png` (light), `preview-dark.png`.

## What changed from v1 Command Center, and why

| Owner feedback | Change |
|---|---|
| Keep the Command Center structure | Same three panes (Previous Searches, centre list, right detail), Ctrl+K palette, filter chips, shortcuts. |
| Light by default, with a toggle | Light is the default; Light/Dark toggle saved in `localStorage` (`cnt-theme`). |
| Liked Company Map grouping and colours | The centre list is a company **tree**: company row (rank, name, job and contact counts, fit bar, pin) expands to nested job and person rows. The detail pane for a company shows Jobs and People side by side, as Company Map did. |
| Liked Linen colours | Linen cream surfaces and warm borders, with Harbor accents (blue primary, violet companies, sky jobs, teal people, amber pins). |

Also: **Expand all / Collapse all**, a **Tree / Flat** toggle (Flat gives Companies / Jobs / People tabs), detail opens on the top company, and the v1 contrast failure is fixed. Cause: the toggle buttons carried `data-theme="dark"`, which re-themed them with the wrong tokens. They now use `data-set`.

Keys: Up/Down move, Right expands or enters the first child, Left collapses or goes to the parent, Home/End, Enter opens detail. P pin, X mark applied/connected, E expand/collapse all, V tree/flat, `/` filter, N new search. Applied/Connected, pin, copy message, find-people (first try errors, retry works) all work.

## Palette

| Token | Light | Dark (warm espresso) |
|---|---|---|
| bg / surface / surface-alt | #FAF6F0 / #FFFCF8 / #F2EBE0 | #1D1815 / #272019 / #342B23 |
| border / input-border | #E4D9C8 / #A8957D | #463A30 / #85766A |
| text / text-2 | #2B2420 / #675A50 | #F4ECE2 / #BDAE9F |
| accent (text, rings) / fill (buttons) | #1D4ED8 / #1D4ED8 | #8EB0FF / #2F5FD9 |
| company / job / person | #6D28D9 / #0369A1 / #0F766E | #C4B5FD / #7DD3FC / #5EEAD4 |
| pinned / applied / connected | #B45309 / #15803D / #4338CA | #FBBF24 / #86EFAC / #A5B4FC |

## Type scale

Space Grotesk for headings and company names (24 detail title, 21 page title, 15 company row, 13 to 14 body rows); IBM Plex Sans for body (14 base, 12.5 meta, 11 uppercase labels).

## Implementation notes

- `styles.css` top block holds all tokens under `:root,[data-theme=light]` and `[data-theme=dark]`; map them to the BoardUI/Tailwind theme variables. Use `--accent` for text and focus, `--fill` for solid button backgrounds (they differ only in dark).
- Category colour is set once per element with `.c-company/.c-job/.c-person` (`--c`); `.pill`, `.chip-icon`, `.avatar`, `.cnt`, `.mc` derive from it via `color-mix`, so pill text is darkened in light mode (`--keep`) and AA holds.
- Tree: `.node.lvl1/.lvl2` with `role=tree`, `treeitem`, `aria-level`, `aria-expanded`, roving `tabindex`. Flat view reuses `.node` with `role=listbox/option`.
- State is keyed by entity key (pins, applied, connected), so every surface updates together.

## Checks

Playwright (Edge): no console errors, no horizontal scroll at 1440 and 390 on all four pages. Text contrast scan (computed colours, AA 4.5:1, 3:1 large) on results in both themes: 0 failures; search, running, library: 0 (the only flag is the gradient-text headline on search, whose two gradient colours both pass).
