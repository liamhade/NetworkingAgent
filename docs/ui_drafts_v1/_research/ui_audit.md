# Networking Agent: UI/UX Audit (read-only research)

Date: 2026-11-15. Frontend: `networking-agent/frontend` (Vite, React 19, TS, Tailwind v4, BoardUI components, react-aria-components, Remix icons). Screenshots (Playwright/Chromium, 1440x900 unless noted) are in `ui_drafts/_research/screenshots/`. Nothing in the repo was changed; no search was started. The agent-progress view could not be screenshotted (needs a running search) and is reconstructed from code.

All source paths are relative to `networking-agent/frontend/src/`.

---

## 1. Inventory of screens and components

### App shell (`App.tsx`)
Flex layout: `[SearchHistory aside 288px, md+ only] [main column: TopNav + page] [SearchConfigs aside, only on Search view + hero state, lg+]`.
Routing is hash based (`utils/view.ts`): `#/` Search, `#/companies`, `#/jobs`, `#/people`. Search has two internal states, `hero` (form) and `results` (a saved or running search). Opening a history item or a "seen in" chip switches to Search > results.

### Screens
| Screen | File | Max width | Components |
|---|---|---|---|
| Hero / search form | `pages/hero.tsx` | `max-w-2xl` (672px) | `FileUpload` (PDF dropzone) or `SavedResumeChip`; `Textarea` x2; `Input`; `SearchBoards` (Accordion; Switch + NumberField per board); primary `Button` "Find opportunities". Shots: `01-hero.png`, `01b-hero-full.png`, `02-hero-boards-open.png` |
| Results (one search) | `pages/results.tsx` | `max-w-3xl` (768px) | ghost "New search" button; `Progress` (while running); `ErrorBanner`; header "Your opportunities" + summary paragraph; ordered list of `CompanyCard`, each with job rows, people rows, `FindPeopleButton`. Shots: `03-results-top.png`, `04-results-full.png`, `05-results-expanded-full.png` |
| Running view | `results.tsx` `Progress` + `components/application/agent-thinking/agent-thinking.tsx` | same | Bordered box: animated 3x3 dot-grid "wave", shimmering latest status line, elapsed timer; caption "Searching job boards and LinkedIn can take a few minutes."; earlier status lines as a plain tertiary list (sample search logged 38 messages, e.g. "Reading your profile", "Planning: ...", "Searching BuiltInNYC jobs for ...", "BuiltInNYC jobs for ...: 15 jobs"). Cancel exists only in the history sidebar. |
| Companies | `pages/entities.tsx` `CompaniesPage` | `max-w-3xl` | H1 + count chip + sort `Select`, blurb, list of company cards. Shot `06-companies*.png` |
| Jobs | `entities.tsx` `JobsPage` | `max-w-3xl` | same; chip shows "3/29 applied". `06-jobs*.png` |
| People | `entities.tsx` `PeoplePage` | `max-w-3xl` | same; chip shows "4/36 connected". `06-people*.png`, `07-people-sort-open.png` |
| Previous searches panel | `components/search-history.tsx` | 288px, sticky | "New search" button; `HistoryBubble` list (title clamped to 2 lines; status Searching / Failed / Cancelled or relative date); delete icon with inline "Delete this search? Keep / Delete"; Cancel on running; "Test User" footer. `hidden md:flex`. |
| Search configurations panel | `components/search-configs.tsx` | right column | "Save current configuration"; config bubbles with rename / overwrite / delete icon buttons (with confirm). Right column from `lg`; stacks under the form with a collapsible list below. Search hero only. |
| Top nav | `components/top-nav.tsx` | `max-w-3xl`, sticky | Pill links Search / Companies / Jobs / People (icon + label, 32px tall). No logo/app name. |

There are NO separate entity detail pages. "Entity detail" = the card in the Companies/Jobs/People lists, which links out (icon on the name) and back to originating searches via "seen in" chips. Company cards on the library page show job/contact counts but these chips are not clickable and the company's jobs/people are not shown.

### Data shown per item

**Company in a search result (`results.tsx CompanyCard`)**: rank number, name (external link), 1-3 line description, chips "Fit 82", "N jobs", "N contacts", pin; "How you align" collapsed lime bar (alignment text 170-280 chars when open); nested sections "JOB OPENINGS" and "PEOPLE TO CONNECT WITH" (or "No current employees found yet."); button "Find People To Connect With" / "Find more people". Not shown: `people_keywords`.

**Job row**: title (link), `location · salary`, NOT APPLIED / APPLIED toggle, pin, "How you align" bar, per-job "Find People To Connect With" button. The job `score` (0-100) is in the data but is NOT rendered anywhere.

**Person row**: name (link to LinkedIn), title, NOT CONNECTED / CONNECTED toggle, pin, "Why connect" lime bar, "Example LinkedIn message" blue bar (expands to text + character count + Copy).

**Library cards (`entities.tsx`)**: same fields; job meta = `company · location · salary`, person meta = `title · company`; footer "Last seen <relative date> · in N searches: [chip] [chip] [chip] +N more"; company card shows job/contact counts and no Fit score.

### Interactive features
Pin (company/job/person); APPLIED / CONNECTED toggles; find-people (per company and per job); connect message copy; resume upload/replace/remove; search boards (enable + max jobs); search configs (save/load/rename/overwrite/delete); history select/cancel/delete; sort select. Sort options: Companies: Most recent, Pinned first, Name A-Z, Most jobs, Most contacts. Jobs: Most recent, Pinned first, Applied first, Not applied first, Title A-Z, Company A-Z. People: Most recent, Pinned first, Connected first, Not connected first, Name A-Z, Company A-Z.

---

## 2. Current design system

Source: `styles/theme.css` (BoardUI export from Figma), `styles/typography.css`, `index.css`. Only light mode is used (a `.dark` block exists, nothing toggles it).

### Color as it appears on screen
Primitives are Tailwind v4 OKLCH defaults except neutral-100 `#f7f7f7`, neutral-200 `#ebebeb`, neutral-925 `#121212`, blue-400 `#3392ff`, slate-200 `#ebeff5`. Hex below are approximate conversions from Tailwind v4 oklch values.

| Role | Token | Value |
|---|---|---|
| Page / card surface | `background-full`, `background-primary-default` | `#ffffff` |
| Subtle fill (icon tiles, soft chips) | `background-secondary-default` | `#f7f7f7` (inputs render `#ebebeb`) |
| Hover / active surface | `background-primary-hover` / `-active` | `#f7f7f7` / `#ebebeb` |
| Card border, separators | `border-button-default`, `separator-border` | `#ebebeb` |
| Text primary | `text-primary` | neutral-950, about `#0a0a0a` |
| Text secondary | `text-secondary` | neutral-500, about `#737373` (about 4.7:1 on white) |
| Text tertiary / placeholder / meta / faint icons | `text-tertiary`, `foreground-icon-tertiary` | neutral-400, about `#a1a1a1` (about 2.6:1 on white, FAILS AA) |
| Accent (CTA, focus ring, switch) | `accent-*` = blue ramp | accent-500 `oklch(62.3% .214 259.8)` about `#3b82f6`; 600 about `#155dfc`; 700 about `#1447e6`; 100 about `#dbeafe` |
| Primary button | `gradient-button-primary-default` | 180deg accent-500 to accent-600 |
| Ghost button (history/config icon buttons, pinned pin) | `button-ghost-*` | bg accent-100, fg accent-700 |
| "How you align" / "Why connect" bar | `notification-success-background` / `state-success-text` | lime-100 `oklch(96.7% .067 122.3)` about `#ecfcca` / lime-800 `oklch(45.3% .124 130.9)` about `#497d00` |
| "Example LinkedIn message" bar | `notification-information-*` | blue-100 about `#dbeafe` / blue-600 about `#155dfc` |
| APPLIED / CONNECTED on | `status-lime-*` | lime-200 about `#d8f999` / lime-800 |
| Off toggle | `CHIP_COLORS.neutral` | `#ebebeb` bg, neutral-500 text |
| Count/fit chips | `CHIP_COLORS.soft` | `#f7f7f7` bg, neutral-500 text |
| Error | `text-error-primary`, `border-error-default` | red-500 about `#fb2c36`, outline only |

Unused but available: purple/orange/cyan/yellow/rose status pairs, `--color-ticket-detail-favorite: #ffb83c` (amber). All accent surfaces re-tint by overriding the 11 `--color-accent-50..950` variables (documented in theme.css).

### Typography
Family Inter (`--font-inter: 'Inter Variable'`, `font-sans`). Utilities are `text-{family}-{weight}` from `typography.css`:

| Utility | Size/line | Used for |
|---|---|---|
| `display-3-semibold` | 40/54, 600 | Hero H1 only |
| `title-1-semibold` | 24/34, 600 | Page H1: "Your opportunities", Companies, Jobs, People |
| `title-3-semibold` | 18/26, 600 | Company name (results and Companies page) |
| `headline-medium` | 16/22, 500 | Hero "Start from your resume" |
| `body-regular` / `body-medium` | 14/20, 400 / 500 | Summary paragraph, job title, person name, nav, buttons |
| `body-2-regular` / `-medium` | 13/18 | Descriptions, meta lines, alignment text, history titles |
| `caption-1-medium` / `-semibold` | 12/16 | Chips, status toggles, uppercase section labels, "seen in" footer, bar labels |

Header sizes per page: Hero H1 40px; Results H1 24px; Companies/Jobs/People H1 24px + 14px blurb; panel headings (Previous searches, Search configurations) and card section headings 12px uppercase tertiary.

### Spacing, radius, elevation
- Page `px-6 py-10` (hero `py-16`); card `p-5`; card gap 16px; in-card gaps 12-16px; nested rows 6px.
- Radius: cards `rounded-3xl` (24px), bars and icon tiles `rounded-xl` (12px), history bubbles `rounded-2xl` with a small top-left corner, chips/toggles `rounded-md` (6px), buttons 8-10px.
- Elevation: none. Cards are 1px `#ebebeb` outlines on white. A single 768px column plus 288px panel leaves much of a 1440px viewport as empty white.

### Components available (`components/base/*`)
Button (primary/secondary/ghost/danger; medium/small/xs), Chip (bold/subtle/caption; orange, lime, rose, yellow, cyan, blue, purple, neutral, gray, soft), Input, Textarea, Select, NumberField, Switch, Accordion, FileUpload, Spinner, AgentThinking (wave/spin/stars/infinity), ScrollFade. Absent: Tabs, Table, Tooltip, Dialog/Drawer, Avatar, Progress bar, Toast (theme has tab/segmented-control tokens that could back them).

---

## 3. Problems, prioritized

### P0: Dull and flat (color)
1. The app is about 95% white and grey. Color appears only as a blue hero CTA, repeated lime "How you align" bars (20-40 per results page), blue "Example LinkedIn message" bars, and lime APPLIED toggles (`04-results-full.png`).
2. Color has no consistent meaning: lime (success) is used for alignment text AND applied/connected; blue is used for CTA, focus, ghost icon buttons (delete/rename) and info bars.
3. No brand identity: no wordmark or app name anywhere (nav starts at "Search"), no imagery; the hero is an H1 over a form.
4. Fit score, the best prioritization signal, is a grey "Fit 82" chip equal in weight to "1 job" and "4 contacts". Job score is never shown.
5. Cards have no shadow, accent edge or hover state; six company cards read as one undifferentiated stack. Entity icon tiles are all grey.
6. Quick win: override `--color-accent-*`; add one warm secondary (amber) for pins/highlights; distinct hue per entity type; reserve green for success states.

### P0: Information overload on results
Measured on the saved search "Software engineering roles, particularly..." (6 companies, 12 jobs, 14 people), 1440x900:
- Page height 4,966px (about 5.5 screens), 6,100px with all bars expanded. Companies page 3,961px, Jobs 5,634px, People 7,827px (36 people).
- Everything renders at once: each company shows all jobs and all people, each row with 4-5 controls (link, status toggle, pin, 1-2 expanders, find-people on jobs). Company header alone has link, 3 chips, pin, expander. Two Sigma (4 jobs, 10 people) is roughly 50 controls and several screens tall inside one card.
- 3 levels of nesting (card > section > row > expander) using same-weight coloured bars at each level, so no single "next action" stands out.
- The same two bars ("How you align" / "Why connect" + "Example LinkedIn message") repeat for every row; "Find People To Connect With" (long label) repeats for every job even though it is infrequent.
- The same job/person appears in the results card and in the Jobs/People library pages with different layouts and no cross-link.
- Progressive disclosure candidates: collapse company cards to a 2-line summary (rank, name, fit, "1 job / 4 people", best job) and expand on click or open a detail pane; show top 2-3 jobs/people then "show all"; show the first sentence of alignment as a preview instead of an empty bar; merge alignment + message into one tabbed/accordion section; move pin/status behind hover or an overflow menu except one primary state; make find-people a company-level action.
- Hero: the saved background fills a 5-row textarea; with boards open the page is 1,100px+ and the CTA is below the fold (`02-hero-boards-open.png`).

### P1: Visual hierarchy
- Company name 18/600 vs job/person 14/500 is a weak step; on the library Jobs/People pages the equivalent title is 14px while the Companies page uses 18px for the same level.
- The facts users scan (location, salary, person title) are 13px tertiary/secondary grey and joined by " · " instead of separate scannable pieces.
- Data glitch visible in `06-people.png`: "Engineering Leader @ Tracksuit · Tracksuit" (title already contains company, then company appended); also "Tracksuit · Tracksuit".
- The 12px uppercase tertiary label style is reused for sidebar headings and card sections, weak as wayfinding in a 5-screen scroll.
- "Your opportunities" H1 is generic and omits the search title/params; there is no stats strip (6 companies / 12 jobs / 14 people / applied).
- Hero H1 (40px) wraps to two lines and is followed by a 14px grey subhead; the form reads as settings, not a landing page.
- Pinned items are only distinguished by a small filled pin; pinning does not reorder or highlight within a results card.

### P1: Navigation
- No way to jump within results: no company index/anchor nav, no collapse-all, no scope tabs (Companies/Jobs/People) for this search; the library pages are global across all searches.
- No filtering anywhere (company, status, pinned, location, score, text search). Sorting exists only on the three library pages (single dropdown beside the H1), not on results, and there is no sort by Fit though results are server-sorted by it.
- Companies library items cannot expand to jobs/people; count chips are not links. Job/person cards show company as plain text with no link to the company or its other jobs. "Seen in" chips are the only cross-links and go to a search, not an entity.
- Top nav mixes a mode (Search) with data libraries; while viewing results "Search" is highlighted with no sign you are inside a results view; returning is only the ghost "New search" (duplicated in the sidebar).
- No view for the user's workflow (pinned / applied / connected / to-do); users must sort "Pinned first" per page.
- History panel is `hidden md:flex`: below 768px there is NO access to previous searches or New search (`08-mobile-hero.png`, `09-mobile-jobs.png`); nav tabs overflow ("People" is clipped at 390px); mobile cards put a 4-line meta block beside the controls.
- History titles are truncated server strings; no per-entry result counts.
- The configs panel exists only on the hero; the sample config "Basic" has an empty `background` (configs do not store the background text here), which looks confusing.

### P1: Affordances
- APPLIED / CONNECTED toggles look like static grey uppercase status pills; the off state ("NOT APPLIED" grey on grey) does not read as clickable, and the check-only-when-on pattern is unusual. Consider "Mark applied" outline button/checkbox that turns into a coloured status.
- Pin is an unlabeled 16px icon in a 28px target with no tooltip.
- Disclosure bars hide all text, so users cannot tell whether content is one sentence or a paragraph; expanded text is 13px.
- Connect message: Copy is inside the expanded box; no "Open LinkedIn" action next to it; the profile link is only the small external icon on the name.
- Name = external link, so the card itself has no in-app click target and no detail view (jobs have no description).
- History delete and config rename/overwrite/delete are identical blue 24px icon buttons without text (pencil/floppy/trash); history delete has inline confirm; configs also confirm (`confirmingId`).
- Hero: submit disabled with no explanation (required marked by a red asterisk only); optional resume dropzone visually dominates the required fields.
- Find-people starts a slow LLM/browser job with no time/cost hint; progress is only a spinner inside a 24px button.

### P2: Empty, loading, error states
- Library: loading = small spinner + "Loading..." (no skeleton); empty = dashed card with grey icon and "No jobs yet. Run a search and they'll show up here." with no CTA button.
- Results: "No matching companies found. Try broadening what you're looking for." is a plain paragraph with no action.
- Running: the dot-wave + shimmer + timer is the nicest moment but the old step lines grow to dozens (38 in the sample) as a plain list; no phase indicator (profile, plan, boards, rank, people); no partial results; Cancel not in the main view.
- Errors: red outline banner with no fill or retry; cancelled/failed searches have no re-run or edit-and-rerun action.
- Sidebar in-progress state: 12px spinner + "Searching..." caption.

### P2: Accessibility
- `text-tertiary` / icon-tertiary `#a1a1a1` is about 2.6:1 on white (needs 4.5:1). Used for meta lines, "seen in", timestamps, placeholders, section headings, "Optional . PDF", unpinned pin icon. Off-state toggle (neutral-500 on neutral-200, about 3.9:1) also fails at 12px.
- Lime-800 on lime-100 (about 6:1) and blue-600 on blue-100 (about 4.8:1) pass but are 12px semibold.
- Positives: focus rings on all controls; `aria-expanded/aria-controls` on bars; react-aria `ToggleButton` (`aria-pressed`); `role="alert"` on errors; `aria-live` on progress; reduced motion honoured in AgentThinking.
- Gaps: dozens of identically named controls ("How you align", "NOT CONNECTED") with no row name for screen readers (only find-people adds a target); heading `h2` contains a link and rank number; targets under 44px (pin 28, status toggle about 24 tall, xs icon buttons 24).

---

## 4. Opportunities summary
1. Real palette: re-tint accent, one hue per entity type, green only for success, amber for pins, visible color-banded fit score.
2. Brand header and use of width: master-detail (company list + selected company's jobs/people) or grid + drawer instead of a 768px column.
3. Results: scoped tabs/segmented control Companies / Jobs / People, filters (pinned, not applied, has contacts, score band), sort-by-fit, stats strip.
4. Collapse by default; one primary action per row, secondary in overflow.
5. Cross-link entities (company from job/person, clickable counts).
6. Pipeline/workflow view for pinned, applied, connected.
7. Mobile: drawer for History and Configs; fix nav overflow.
8. Raise tertiary text contrast; stronger off-state toggle.

---

## 5. Constraints for redesigners

### Real data shapes
Source: `database/users/TEST_USER/searches/7258900d1d3b416ebedf5c53cad61f0c.json` (a search has `id, title, created_at, status, request, results{summary, companies[]}, messages[], error, trace`). Personal details are as stored in the test fixture.

Search summary (history row): `{ "id": "7258900d1d3b416ebedf5c53cad61f0c", "title": "Software engineering roles, particularly… · New York, NY", "created_at": "2026-11-14T20:45:06.493942Z", "status": "done" }` (status: running | done | error | cancelled).

Search request (the same shape as a saved configuration's `params`; configs add `id`, `name`):
```json
{ "background": "I am a Software Engineer at Dover Corporation since November 2025, building an agentic chat interface with self-hosted LLMs ... (about 900 chars)",
  "location": "New York, NY",
  "looking_for": "Software engineering roles, particularly in agentic AI, LLM applications, and backend or data infrastructure. Python or C++ oriented would be ideal.",
  "boards": { "builtin_nyc": {"enabled": true, "max_jobs": 40}, "conservation": {"enabled": false, "max_jobs": 45},
              "greenhouse": {"enabled": false, "max_jobs": 8}, "lever": {"enabled": true, "max_jobs": 8},
              "ashby": {"enabled": true, "max_jobs": 8}, "workable": {"enabled": true, "max_jobs": 8},
              "usajobs": {"enabled": false, "max_jobs": 20}, "google": {"enabled": true, "max_jobs": 20} } }
```
Board metadata comes from the backend (`BoardInfo`: id, label, description, available, unavailable_reason, default, min_jobs, max_jobs), e.g. "Built In NYC: New York City tech companies and their jobs."; "Google job searches: General Google searches for postings the other boards miss. Slow."; "USAJOBS: Needs an API key (USAJOBS_API_KEY and USAJOBS_EMAIL)" (disabled).

Results summary (about 450 chars): "You are targeting agentic AI, LLM application and backend roles in New York, with a preference for Python or C++. The strongest matches are Tracksuit's production AI agent role, Two Sigma's Python and C++ quant engineering roles, and Citadel's Python engineering roles. Alchemi, Palantir and Capital One have relevant AI roles, but they are less certain fits on seniority or posting detail."

Company (real companies have 0-4 jobs and 0-10 people; one of each shown):
```json
{ "key": "company:name:tracksuit",
  "name": "Tracksuit",
  "url": "https://www.builtinnyc.com/company/tracksuit",
  "description": "Brand tracking platform that helps marketers prove their brand building is working, with offices in New York, London, Sydney and Auckland.",
  "alignment": "You have shipped LLM tooling and MCP integrations at Dover, which matches Tracksuit's focus on production AI agents and MCP servers for go-to-market teams. Your work on a DSCSA-compliant pharmaceutical database also shows you can own production systems end to end.",
  "score": 82,
  "people_searched": true,
  "people_keywords": ["AI engineering manager", "go-to-market engineering lead"],
  "jobs": [ { ...job } ], "people": [ { ...person } ] }
```
Job (`score` optional; `salary`/`location` may be empty):
```json
{ "key": "job:url:builtinnyc.com/job/ai-engineer-gtm/12251267",
  "title": "AI Engineer - GTM",
  "url": "https://www.builtinnyc.com/job/ai-engineer-gtm/12251267",
  "location": "New York, NY, USA",
  "salary": "162K-205K Annually",
  "alignment": "You already build self-hosted LLM agents and custom MCPs, which maps directly to this role's agent and MCP server work. The posting asks for LLM work in production, and your Dover experience covers that.",
  "score": 85 }
```
Person (`connect_message` optional on older searches, about 190-240 chars):
```json
{ "key": "person:linkedin:keniel-yao",
  "name": "Keniel Yao",
  "title": "Head of Data Science",
  "profile_url": "https://www.linkedin.com/in/keniel-yao",
  "alignment": "As Head of Data Science, Keniel leads AI product work at Tracksuit, which is close to the LLM applications you build at Dover. A short conversation could help you understand how the team ships LLM products.",
  "connect_message": "Hi Keniel, I'm a software engineer building an agentic chat interface with self-hosted LLMs and custom MCPs at Dover, so Tracksuit's production AI agent work caught my eye. I'd love to connect and hear how your team ships LLM products." }
```
Library (Companies/Jobs/People pages) entities are the same fields flattened plus `first_seen`, `last_seen` (ISO), `searches: [{id, title, created_at, status}]` (most recent first); jobs/people add `company`, `company_key`; companies add `job_count`, `person_count`.

Per-user state keyed by entity `key` (separate files): `statuses.json` = `{"job": {"job:url:...": {"active": true, "updated_at": "..."}}, "person": {"person:linkedin:...": {...}}}` (currently 3 job and 5 person entries); `pins.json` = `{"company": {"company:name:two sigma": {"pinned": true, ...}}, "job": {}, "person": {...}}`.

Dataset size: 4 saved searches (3 with results); the sample has 6 companies / 12 jobs / 14 people (18.6 KB). Across searches the library holds 29 jobs and 36 people. Company fit scores in the sample range 60-82. Dates render relative ("Yesterday, 3:45 PM") with the full date in a tooltip.

### Features that must be preserved
1. Search form: background (required), location, looking_for (required); resume PDF upload that auto-fills fields; saved-resume chip with download / replace / remove; search boards panel (per-board enable switch, max-jobs number within min/max, unavailable boards disabled with reason, at least one board required or submit disabled); "Find opportunities" submit; draft auto-saved as search params.
2. Search configurations: save current form as named config; load into form; rename; overwrite with current form; delete (with confirm).
3. Previous searches: most recent first; status (Searching / Failed / Cancelled / done) and relative date; click to open (running ones re-attach to live progress); Cancel on running; Delete with confirmation on non-running; New search; user display name (account slot needed: multi-user is planned).
4. Running view: live status lines, timer, "can take a few minutes" notice, results on completion; failed/cancelled states with message and step log.
5. Results: ranked companies (server-sorted by fit), summary; per company name link, description, Fit score, job/contact counts, pin, alignment text; jobs (title link, location, salary, applied toggle, pin, alignment, per-job Find people); people (name link, title, connected toggle, pin, "Why connect", example LinkedIn message with Copy + character count); company-level "Find People To Connect With" / "Find more people" (disabled until the search is saved; independent loading/error/retry per button; several can run concurrently); empty states ("No current employees found yet", "No matching companies found").
6. Library pages Companies / Jobs / People: counts ("3/29 applied", "4/36 connected"), the sort options above, pin, statuses, last-seen and links to up to 3 originating searches then "+N more", empty/error/loading states, hash routes `#/companies`, `#/jobs`, `#/people`.
7. State is keyed by server entity `key`, so one job/person shows the same applied/connected/pinned state everywhere and must update on every surface instantly.
8. Accessibility contract: accessible names on icon-only buttons (pin "Pin <name>", "Delete search: <title>"), keyboard operability, `aria-pressed` on toggles, `aria-expanded` on disclosures, visible focus rings.

### Technical constraints for HTML mockups
- Stack: Tailwind v4 utilities + BoardUI tokens; use existing token names (`text-text-primary`, `bg-background-secondary-default`, `border-border-button-default`, `accent-*`) or define new ones explicitly so porting is mechanical. Font Inter. Light mode.
- Icons: Remix (`Ri*Line` / `Ri*Fill`). Reusable components: Button, Chip, Select, Accordion, Switch, NumberField, Input, Textarea, FileUpload, Spinner, AgentThinking.
- Current layout assumptions: 288px left history panel (md+), right configs panel (lg+, hero only), main column 672px (hero) / 768px (other pages), sticky 48px top nav.
- Backend does not yet support server-side filtering/sorting, entity detail endpoints, job descriptions, notes, or statuses beyond the boolean toggles; designs needing these should be marked future work.
- Use the saved searches in `database/users/TEST_USER/searches/` as fixtures; never start a live search to test a design.

---

## Screenshot list
`ui_drafts/_research/screenshots/`
- `01-hero.png`, `01b-hero-full.png`: landing form with Previous Searches (left) and Search Configurations (right)
- `02-hero-boards-open.png`: Search boards expanded (full-page capture; sticky panels render offset)
- `03-results-top.png`, `04-results-full.png` (4,966px), `05-results-expanded-full.png` (6,100px): completed results
- `06-companies.png`, `06-companies-full.png`, `06-jobs.png`, `06-jobs-full.png`, `06-people.png`, `06-people-full.png`: library pages
- `07-people-sort-open.png`: sort dropdown
- `08-mobile-hero.png`, `09-mobile-jobs.png`: 390px mobile (history panel absent, nav clipped)
- Not captured: agent-progress view (requires starting a search); pin/status toggles were not clicked to avoid mutating `database/users/TEST_USER/{pins,statuses}.json`.
