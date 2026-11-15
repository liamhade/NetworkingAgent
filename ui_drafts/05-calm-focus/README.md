# Direction 5: Calm Focus (Sage)

Open `results.html` first (also `search.html`, `running.html`). Static files, no build; `styles.css` and `shell.js` are shared.

## Problems fixed (audit refs)
- **Dull / flat (P0):** sage-tinted neutrals, forest-green sidebar and CTA, one hue per entity (company violet, job teal, person amber), amber for pins and highlights, green reserved for success. Brand wordmark added.
- **Information overload (P0):** one tab at a time, 2-column cards, 4 shown then "Show 5 more" with a progress bar. Alignment clamped to 2 lines; "Why it fits" expands in place (message + Copy for people). A drawer holds the rest. Max two disclosure levels.
- **Fit score buried (P0):** coloured Fit pill (Strong 80+, Good 70+, Possible); job score finally rendered.
- **Hierarchy (P1):** 28/24/19/16 type steps; "Start here: top picks" band gives a first answer.
- **Navigation (P1):** tab counts, pinned / not-done filters, sort, company chips on jobs and people jump to the company; "3 jobs / 4 people" chips on a company filter the other tabs (link kept despite tabs). Previous searches become a drawer on mobile.
- **Affordances (P1):** statuses are visible checkbox-buttons ("Mark applied" to green "Applied"); pin has label, fill pop and toast.
- **Running (P2):** five named phases, orb with percent, live line, elapsed time, Cancel in-page, early finds with live counts and skeletons, cancelled and finished states.
- **A11y:** AA text pairs, 40-48px targets, aria-pressed/expanded, focus rings, dialog focus trap + Esc, reduced-motion.

## Palette (Sage)
bg #F5F7F2, surface #FFFFFF, surface-alt #E9EEE3, border #D6DECD, input border #7F8F82, text #1F2A22, text-2 #52635A, accent #2F6B4F / hover #245640, forest (sidebar) #1E3B2C, company #6B4E9B (ink #563C82), job #0E6B7A (ink #0B5A67), person #9A5B13 (ink #7E4A0E), pinned #8A6A00 (ink #6F5500), applied #166534, connected #1F5F8B. Pill text uses the darker "ink" so tinted pills stay above 4.5:1. Highlights: butter #F1DE9B.

## Type
Inter Tight (headings) + Inter (body). h1 28 (hero 46), h2 24, h3 card name 19, body 15-16, meta 13-14, pills 12.5. Tabular numbers on counts.

## IA
Sticky header (title, progress ring, tabs) > summary > top picks > toolbar (filters, sort) > card grid > Show more. Progress ring = done / (pinned or done jobs and people).

## Implementation notes
- Override `--color-accent-*`, text/background tokens in `theme.css` with the values above; add `--color-company/job/person/pinned` tokens.
- New components: Tabs, Drawer (react-aria Modal), ProgressRing, FitPill, StatusToggle (replaces APPLIED/CONNECTED chip), TopPicks, ShowMore, Sidebar drawer on mobile.
- Refactor `results.tsx`: split `CompanyCard` into flat Company/Job/Person cards, flatten data by entity.
- Future/backend: company-to-entity cross filter is client-side; "Edit and re-run" and example search are UI only.

## Compromises
Companies/Jobs/People nav links point at results tabs (no separate library page drawn). Plan ring semantic is a mockup assumption. Delete/cancel confirmations in the sidebar are demo-only.
