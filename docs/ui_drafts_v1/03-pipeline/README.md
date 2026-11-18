# Direction 3 "Pipeline" (Palette C "Pop")

Open `results.html` (centrepiece), `search.html`, `running.html`, `library.html?type=jobs|people|companies`. Static, no build; `preview.png` is the 1440px results page.

## Idea
Results are a job-hunt funnel from the first second. Each company is a **swim lane**; its jobs and people are compact cards that move across four columns: **New, Shortlisted, Applied / Connected, Following up**. A Board/List toggle gives a plain grouped list (also the mobile default). Cards show only name, one meta line, fit and status; the full "Why it fits / Why connect", the LinkedIn message (Copy) and external links live in a **details drawer** (one level only, never a drawer from a drawer).

## Audit problems fixed
- Dull/flat (P0): cream page, violet action colour, one hue per entity (company magenta, job teal, person orange), pinned amber, applied green, connected blue. Colour has one meaning each; green is only success.
- Information overload (P0): notes, messages and secondary actions leave the page. Lanes collapse; type/filter chips (Pinned, To do, Strong fit 75+) and a "Start here" band replace a 5-screen scroll.
- Fit hidden: Fit is a banded pill (violet 75+, amber 65-74, grey below); job scores (never shown today) appear on job cards.
- Hierarchy: h1 28 / lane name 20 / card title 15 / meta 13 / pill 12. Search title and counts replace "Your opportunities".
- Navigation: sticky toolbar with progress ("3 of 20 actions done"), sort, view toggle; Previous Searches kept, with Cancel on running; mobile gets an off-canvas sidebar and no clipped nav.
- Affordances: "Mark applied" is an outlined button that fills green when on; pin has an accessible name; Copy gives inline and toast feedback.
- Contrast: no tertiary grey; text-2 `#5B5075` only. Pop's company colour `#C026D3` (4.56:1) is replaced by `#A21CAF` for icons/text and `#86198F` on tints.
- Running (new): stepper, timer, Cancel in the main view, items stream into the New column with skeletons.

## Palette
bg `#FFFBF2`, surface `#FFFFFF`, alt `#FFF1D6`, border `#EADFC6` (inputs `#9C8F72`), text `#1A1033`, text-2 `#5B5075`, accent `#7C3AED` (hover `#6D28D9`), company `#A21CAF`, job `#0E7490`, person `#C2410C`, pinned `#A16207`, applied `#047857`, connected `#1D4ED8`. Pill text uses 800-step inks (`#86198F #155E75 #9A3412 #854D0E #065F46 #1E40AF`) on ~12% tints.

## Type
Plus Jakarta Sans only. 46 hero / 28 h1 / 20 lane / 15 body + card title / 13 meta / 12 pill (700-800). Tabular numerals on counts and fit.

## Status mapping and proposed features
- Real: Pin = Shortlisted; APPLIED (jobs) / CONNECTED (people) = Applied / Connected; New = neither.
- **PROPOSED, needs new backend state:** the "Following up" column (marked "Proposed" in the UI). Also not in the backend: server-side filters/sort, "Find more people" simulated here, Start here ranking, per-search progress stages and partial results, library "seen in" deep links, rename-in-place for configs.
- Drag-and-drop works within a lane only (cards belong to their company); buttons and the drawer's "Move to column" are the keyboard path.

## Code changes needed
- `styles/theme.css`: override `--color-accent-*` with a violet ramp; add `--color-company/job/person/pinned/applied/connected` plus ink/tint pairs; replace `text-tertiary` usages with text-2; load Plus Jakarta Sans (replace Inter).
- New components: `Lane`, `Board`, `PipelineCard`, `Drawer`, `Segmented`, `FilterChip`, `Stepper`/`RunCard`, `FitPill`. Rework `results.tsx` (CompanyCard becomes Lane header), `top-nav.tsx` (add wordmark), `search-history.tsx` (restyle, unchanged logic), `hero.tsx` (restyle; boards accordion unchanged), `entities.tsx` (rows with entity icon, status button).
- Reuse: Button, Chip, Switch, NumberField, Input, Textarea, Accordion, Spinner. Statuses/pins keep keying on entity `key`.

## Compromises
Board needs width (~1000px+); below 820px it collapses to the list. Four columns for one company can look sparse early on. Drag cannot cross lanes.
