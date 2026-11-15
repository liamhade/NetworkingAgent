# Direction 4: "Company Map" (Harbor palette)

Open `results.html` (centrepiece), then `search.html`, `running.html`, `library.html#jobs`. All static; shared `styles.css`, `shell.js` (nav, sidebar, icons), `data.js` (real sample data from the Tracksuit/Two Sigma search). `preview.png` is the 1440px result.

## Problems fixed (audit refs)
- **Overload (P0):** page was 4,966px with everything expanded. Companies are now 76px summary rows (rank, name, one-line description, best-match job, jobs/people counts, fit meter, pin). Only the top company is open; "Expand/Collapse all" exist. Within a panel, 3 jobs/3 people show, then "Show N more". Notes sit behind "How you align" / "Why connect" disclosures; "Find people" is one company-level button (per-job version lives inside the job's note).
- **Dull colour (P0):** Harbor palette, one hue per entity (violet companies, sky jobs, teal people), amber only for pins, green only for Applied, indigo for connected. Colour on small elements and left stripes, not whole cards.
- **Fit signal buried:** fit is a large coloured number plus bar and label ("Strong fit"); job score shown as "85 match" (it was never rendered).
- **Navigation (P1):** sticky "Jump to company" index with scores; sticky toolbar with Group by Company | Type, filter chips (Has open job, Has contact, Strong fit, Not applied, Pinned), sort. Stats strip and a "Start here" action. Cross-links: "Message Keniel about AI Engineer - GTM", job rows show contacts, type view has company tags that jump back.
- **Affordances:** status toggles are dashed "Mark applied" outlines that become solid green/indigo with a check (never colour alone); pins have labels and an Undo toast; connect message lives in a side drawer (role select, tone, live count/300, Copy with feedback, Open LinkedIn, Mark connected). Running page has Cancel in the main view, stage stepper, live log and results streaming in. Sidebar works as an off-canvas menu on mobile.
- **Contrast:** no grey below #516179 (5.9:1); all pill text uses 700-800 steps.

## Palette (Harbor)
bg #F4F7FB, surface #FFFFFF, surface-alt #E8EEF6, border #D5DEEA, input border #8A9BB3, text #0F1E33, text-2 #516179, accent #1D4ED8 (hover #1E40AF), company #6D28D9, job #0369A1, person #0F766E, pinned #B45309, applied #15803D, connected #4338CA. Pill text uses darker steps (#5B21B6, #075985, #115E59, #92400E, #166534, #3730A3) on 10% tints.

## Type scale
Manrope headings, Public Sans body. h1 30/800, company name 20/800, section h2 22/800, row title 15.5/700, body 15, meta 13.5, pills 12.5/700. Tabular numerals for scores and counts.

## Porting to the real code
- `theme.css`: override `--color-accent-*` with the blue ramp; add `--color-company/job/person/pinned/applied/connected` plus `-tint` tokens; add Manrope/Public Sans (or keep Inter and drop the heading font).
- Rework `CompanyCard` in `pages/results.tsx` into a collapsible panel (Accordion) with the two-pane body; add a `FitMeter`, `StatusToggle` (outline to filled) and `EntityChip` component to `components/base`.
- New: `Drawer` (react-aria Modal) for the connect message, `SegmentedControl` for Group by, filter `ToggleButton` chips, jump index, stats strip (all client-side over existing data).
- `SearchHistory` becomes a mobile drawer; `TopNav` gets a wordmark.
- Future backend work: persisted regenerated messages and tone options (mockup only), real progress stages and partial results streaming (the running view assumes stage + found-so-far events).
