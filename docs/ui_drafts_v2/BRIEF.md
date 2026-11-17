# UI drafts v2: brief

Second round of mockups, based on the owner's feedback in [updating-ui.md](../updating-ui.md) on the v1 drafts in [ui_drafts_v1/](../ui_drafts_v1/index.html).

## Feedback, distilled

| v1 draft | Verdict | What carries forward |
|---|---|---|
| 01 Field Notes | Colours yes, format no | The **Linen** palette (cream surfaces, terracotta accent, violet/teal/amber entity colours) |
| 02 Command Center | Structure yes, dark default no | The **three-pane layout** (searches sidebar, list, detail pane), tabs, filter chips, keyboard shortcuts. It must be **light by default with a light/dark toggle** |
| 03 Pipeline | No | Nothing (no kanban) |
| 04 Company Map | Results page yes, colours yes | The **company-grouped results** (collapsed company panels, jump-to index, jobs and people side by side, cross-links) and the **Harbor** palette |
| 05 Calm Focus | No | Nothing (no low-density tabbed cards) |

## Rules for every v2 draft

- Light theme by default, with a working light/dark toggle saved in `localStorage`. Dark mode must be a tinted dark (warm or navy), not near-black grey.
- Must keep every feature listed in `docs/ui_drafts_v1/_research/ui_audit.md` §5.
- Must pass WCAG AA in both themes, including inactive toggle and button labels (v1 Command Center failed this).
- Static HTML that opens with a double-click; results, search and running pages, plus a README and a preview image.

## The five directions

| # | Folder | Structure | Palette |
|---|---|---|---|
| 1 | `01-command-linen` | Command Center three-pane layout | Linen |
| 2 | `02-command-harbor` | Command Center three-pane layout | Harbor |
| 3 | `03-map-split` | Company Map results in the centre, with Command Center's detail pane on the right | Harbor |
| 4 | `04-map-linen` | Company Map results page, header tightened | Linen |
| 5 | `05-command-tree` | Command Center three-pane layout; the list pane is a company tree (company, then its jobs and people) | Linen surfaces with Harbor's blue/violet accents |

The idea: drafts 1/2 and 3/4 each compare the same layout in both liked palettes, while drafts 3 and 5 try two different ways to merge the liked layouts.
