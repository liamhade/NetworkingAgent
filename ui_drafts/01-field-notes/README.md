# Direction 1: "Field Notes" (editorial, warm, Palette A "Linen")

Open `results.html` first. Also: `search.html` (form), `running.html` (live search with Running / Cancelled / Failed switcher bottom-right). `styles.css` and `shell.js` (sidebar, nav, icons, toast) are shared. `preview.png` is the 1440px results page.

## Audit problems fixed
- **Dull / flat (P0):** warm cream surfaces, terracotta action colour, one hue per entity (violet company, teal job, amber-brown person), green only for Applied, blue only for Connected, gold only for pins. Fit becomes a coloured ring.
- **Information overload (P0):** one scrolling page, but everything is collapsed to one-line rows. Companies are accordions; each job/person shows only a one-sentence preview with "Why it fits you" / "Example LinkedIn message" expanding in place (two disclosure levels, no more). The long "Find people" button appears once per company.
- **Hierarchy (P1):** serif H1 (40) / H2 (24) / company (20) vs 16 px item names; location and salary are separate scannable pieces; a stats strip and a "Start here" band give the page a first answer.
- **Navigation (P1):** sticky controls (By company / Jobs / People with counts, Pinned / To do / Strong fit filters, sort), "Jump to" rail, progress rail (applied/connected/pinned), cross-links ("See Tracksuit"). Mobile gets a drawer for Previous searches.
- **Affordances:** status buttons read as buttons ("Mark applied" dashed, then green "Applied" with a tick); pins have labels and an Undo toast; copy gives "Copied".
- **Running:** 5-step stepper, elapsed time, Cancel in the main view (inline confirm), results streaming into "Found so far", failed/cancelled states with retry.
- **A11y:** all text pairs AA (pill text uses darker -ink steps); tertiary grey removed; aria-expanded/pressed, visible focus rings, reduced-motion respected.

## Palette (Linen)
bg #FAF6F0, surface #FFFFFF, surface-alt #F2EBE0, border #E4D9C8 (inputs #A8957D), text #2B2420, text-2 #6B5E54, accent #C2410C / hover #9A3412, company #7C3AED (text #5B21B6), job #0F766E (#115E59), person #B45309 (#92400E), pinned #A16207, applied #15803D, connected #1D4ED8. Person vs accent are close, so people use round initials avatars and the accent is limited to buttons/fit rings.

## Type
Fraunces (headings, soft, optical size) + Source Sans 3. H1 40/1.12, H2 24, company 20, item 16 bold, body 15 to 15.5, meta 14, pill/label 12 to 13. Tabular numerals on counts and scores.

## Porting to the real code
- Replace `theme.css` tokens: `--color-accent-*` ramp (terracotta), background/text/border tokens, add `company/job/person/pinned/applied/connected` tokens; load Fraunces + Source Sans 3.
- New or changed components: `results.tsx` (header, stats, Start here, sticky controls), `CompanyCard` becomes an accordion with nested rows, add Tabs/Segmented, FitRing, StatusButton, Disclosure, Toast, mobile drawer for `SearchHistory`, Progress stepper in `AgentThinking`.
- Fit-based "Start here" and score filter use existing `score`; job score is now shown. Server-side filtering is not needed (client-side here).

## Compromises
Companies/Jobs/People nav items open this search's results in the matching view rather than the global libraries; the library pages would reuse the same row components. The "Start here" picks are hard-picked in the mock (derive from top scores in real code). Find people is simulated.
