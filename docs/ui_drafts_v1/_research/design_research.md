# Networking Agent: UI Design Research

Scope: make the UI more pleasing, easier to understand and more intuitive. Items are companies, jobs and people. Each has an alignment note, a pin, a status (APPLIED or CONNECTED) and a generated connect message. The agent runs in the background and users revisit previous searches.

Sources marked (fetched) were read for this document. Sources marked (background) are cited from expertise and were not fetched.

---

## 1. Key principles

### 1.1 Progressive disclosure
- Show only the few most important items first. Put specialist content on a secondary level that opens on request. Placement signals importance, so whatever is on the first screen is read as "this matters". NN/g, Progressive Disclosure (fetched): https://www.nngroup.com/articles/progressive-disclosure/
- Use two levels at most. Designs with three or more disclosure levels "typically have low usability".
- Make the control that opens the next level obvious and specific. Say "Why this fits (3 points)" rather than "More".
- Offer one route to each secondary level. Avoid several routes to the same content.
- For this app, level 1 is the row or card: name, one-line reason, status and pin. Level 2 is the full alignment note, evidence and the connect message. Do not add a third level. A drawer or modal can sit at level 2 as long as it does not open another drawer.

### 1.2 Information scent and labels
- Labels carry most of the scent. Make them specific, avoid jargon and branded terms, and make them stand on their own without relying on nearby context. NN/g, Information Scent (fetched): https://www.nngroup.com/articles/information-scent/
- Replace internal wording such as "alignment" with outcome wording such as "Why it fits you". Use tab and section labels with counts, for example "Jobs 12".
- Write the one-line summary of each alignment note so it starts with the most informative words, for example "Series B fintech hiring 3 PMs, matches your payments background".

### 1.3 Scanning patterns and heading hierarchy
- Users scan rather than read. The pattern is often F-shaped: the top, then a shorter line lower down, then the left edge. Content on the right or lower down gets skipped. NN/g, F-Shaped Pattern (fetched): https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- Their recommendations apply directly:
  - Give headings visual weight that differs clearly from body text.
  - Start headings with the most informative words.
  - Group small related blocks with a border or background.
  - Bold key phrases sparingly.
  - Use bullets for lists.
  - Cut text.
- Put the entity name on the left edge, bold. Put the status and actions on the right as small controls, not as the first thing the eye lands on.

### 1.4 Cards or lists
- Cards suit browsing and mixed content. Lists suit scanning, comparing and showing more at once, because fixed positions are easier to scan. NN/g, Cards (fetched): https://www.nngroup.com/articles/cards-component/
- This app has three entity types with different shapes, which favours cards. Within one type the user compares like with like, which favours dense rows. So use a dense row for lists of 10 or more, and a card only for the top picks or a drawer.

### 1.5 Tabs and accordions
- Use tabs on desktop and accordions on mobile. Accordions that are all closed make a desktop page look empty. Avoid tabs when users need to compare across sections. Keep tab sets small with short labels. NN/g, Tabs, Used Right (fetched): https://www.nngroup.com/articles/tabs-used-right/
- Three entity tabs are fine because the set is small. Since companies, jobs and people relate to each other, give a cross-tab link such as "3 jobs, 2 people at this company" so users do not have to compare by switching tabs.

### 1.6 Colour usage (Refactoring UI, Radix, Material 3)
- Grey ramp: about 8 to 10 shades, starting from a very dark grey rather than pure black. One or two primary colours with 5 to 10 shades each. Accent colours for semantic states, used sparingly. Define the shades up front and do not generate them with "lighten" or "darken". Refactoring UI, Building Your Color Palette (fetched): https://www.refactoringui.com/previews/building-your-color-palette
- Radix 12-step scale roles (fetched): https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
  - Steps 1-2: app and subtle backgrounds.
  - Steps 3-5: component background, hover and pressed.
  - Steps 6-8: borders (6 subtle, 7 interactive, 8 strong and focus ring).
  - Steps 9-10: solid fills and their hover.
  - Steps 11-12: low-contrast and high-contrast text.
  - Steps 11 and 12 are tuned to Lc 60 and Lc 90 APCA on a step 2 background of the same scale.
- Tint the neutrals toward the brand hue (warm, cool or green-grey) instead of using pure grey. This is the cheapest change that stops the UI feeling dull.
- One saturated primary colour for actions only. Category colours (company, job, person) go on small elements: icon chips, left-edge stripes and pills. Do not colour whole cards.
- Never rely on colour alone. Pair each status colour with an icon or text label. Cover colour-blind users by also varying the icon shape per category.
- Material 3 colour roles (background, surface, surface-container, on-colour, tonal containers) are the model for the surface and surface-alt tokens used below (background): https://m3.material.io/styles/color/roles
- WCAG 2.2 AA (background): text of 4.5:1 or more, large text and UI component boundaries of 3:1 or more. https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- Tailwind v4 defines palettes in OKLCH and supports custom theme variables with `@theme` (background): https://tailwindcss.com/docs/theme

### 1.7 Density control (background)
- Linear, Notion and Attio all offer compact and comfortable densities. Row height is the main control (32 px, 44 px, 64 px). Do not remove information. Move it behind progressive disclosure.
- A density toggle (Compact, Comfortable) is cheap and lets one UI serve both the first result skim and the later pipeline work.
- Use de-emphasis rather than deletion. Make secondary data smaller, lighter and grey instead of removing it (Refactoring UI hierarchy ideas). Keep at most three text tones on a row: primary, secondary and tertiary.

### 1.8 Pattern inspiration (background; not fetched)
- LinkedIn Jobs: master-detail with a list on the left and a detail pane on the right, and "Easy Apply" style status chips on rows.
- Wellfound and Otta / Welcome to the Jungle: card with a match label and a short "why" bulleted list. Otta's match reasons are the closest analogue to the alignment note.
- Linear: neutral, dense, keyboard-first, with status icons rather than words and subtle hover rows.
- Notion: grouped lists with collapsible groups and counts in the group header.
- Attio: relationship-centric record pages and saved views as tabs.
- Huntr and Teal: kanban pipeline of saved, applied, interviewing and offer.

---

## 2. Colour palette proposals

Token names: `bg`, `surface`, `surface-alt`, `border`, `text`, `text-2`, `accent`, `accent-hover`. Category colours are company, job and person. Status colours are pinned, applied and connected.

Contrast ratios were computed with the WCAG relative luminance formula. "text on bg" uses the `text` token on the `bg` token, and so on. Every pairing listed is 4.5:1 or more unless marked.

Pill advice for all palettes: fill the pill with the category colour at about 12% over the surface, and use the category colour or a darker step of it for the text. On a 12% tint the listed colour measures 3.9 to 4.8:1 (for example `#C2410C` on its tint is 4.35, `#B45309` on its tint is 4.25). So for light palettes darken the pill text one step (Tailwind 700 to 800) or use the pill with a 1 px border and a darker text colour. Re-check each pill pairing when building.

### A. "Linen" (light, warm)
Mood: friendly, editorial, calm. Cream paper with a terracotta action colour. Feels human and low-pressure for a stressful activity.

| Token | Hex | Notes |
|---|---|---|
| bg | #FAF6F0 | warm off-white |
| surface | #FFFFFF | cards |
| surface-alt | #F2EBE0 | hover, headers, inset |
| border | #E4D9C8 | decorative only (about 1.4:1, fine for separators; use #A8957D for input outlines, about 3:1) |
| text | #2B2420 | 14.18:1 on bg, 15.26:1 on surface |
| text-2 | #6B5E54 | 5.82:1 on bg, 5.29:1 on surface-alt |
| accent | #C2410C | white text on it 5.18:1; on bg 4.81:1 |
| accent-hover | #9A3412 | darker, so white text stays above 7:1 |
| company | #7C3AED | 5.29:1 on bg |
| job | #0F766E | 5.08:1 on bg |
| person | #B45309 | 4.66:1 on bg |
| pinned | #A16207 | 4.57:1 on bg |
| applied | #15803D | 4.66:1 on bg |
| connected | #1D4ED8 | 6.22:1 on bg |

Note: the accent and the person colour are both warm orange-browns, so give person a person icon and a different shape. If that is too close, swap the accent to a deep rose (#BE123C, about 5.9:1 on white).

### B. "Harbor" (light, cool and professional)
Mood: trustworthy, business-like, close to LinkedIn and Linear but with more colour. Pale blue-grey background and a strong blue primary.

| Token | Hex | Notes |
|---|---|---|
| bg | #F4F7FB | |
| surface | #FFFFFF | |
| surface-alt | #E8EEF6 | |
| border | #D5DEEA | decorative; inputs #8A9BB3 (about 3:1) |
| text | #0F1E33 | 15.59:1 on bg |
| text-2 | #516179 | 5.86:1 on bg, 5.39:1 on surface-alt |
| accent | #1D4ED8 | white on it 6.70:1 |
| accent-hover | #1E40AF | |
| company | #6D28D9 | 6.61:1 on bg |
| job | #0369A1 | 5.52:1 on bg |
| person | #0F766E | 5.09:1 on bg |
| pinned | #B45309 | 4.67:1 on bg |
| applied | #15803D | 4.67:1 on bg |
| connected | #4338CA | 7.36:1 on bg |

Note: job (sky blue) and the blue accent are related. Keep the accent for buttons only and use the icon shape to separate job from action.

### C. "Pop" (light, bold and vibrant)
Mood: energetic, playful, a little startup-like. Warm cream background with a vivid violet primary and a saturated category palette. Best for a product that wants personality.

| Token | Hex | Notes |
|---|---|---|
| bg | #FFFBF2 | |
| surface | #FFFFFF | |
| surface-alt | #FFF1D6 | butter yellow for highlights and sticky bars |
| border | #EADFC6 | decorative; inputs #9C8F72 |
| text | #1A1033 | 17.44:1 on bg |
| text-2 | #5B5075 | 7.14:1 on bg, 6.60:1 on surface-alt |
| accent | #7C3AED | white on it 5.70:1 |
| accent-hover | #6D28D9 | |
| company | #C026D3 | 4.56:1 on bg (barely AA; use for icons and text of 14 px bold or more, or darken to #A21CAF) |
| job | #0E7490 | 5.19:1 on bg |
| person | #C2410C | 5.01:1 on bg |
| pinned | #A16207 | 4.77:1 on bg |
| applied | #047857 | 5.31:1 on bg |
| connected | #1D4ED8 | 6.49:1 on bg |

Note: the accent is violet and the company colour is magenta, so they sit close. If both appear on one screen, make the company colour fuchsia-700 (#A21CAF) and keep it to the chip only.

### D. "Midnight" (dark mode)
Mood: focused, tool-like, easy on the eyes for long sessions. Blue-black neutrals (not pure black) with a mint accent. Pastel category colours on dark surfaces.

| Token | Hex | Notes |
|---|---|---|
| bg | #0E1116 | |
| surface | #161B22 | |
| surface-alt | #1E252E | |
| border | #2A323D | decorative; inputs #566273 (about 3:1) |
| text | #E8ECF1 | 15.94:1 on bg, 14.58:1 on surface |
| text-2 | #9AA7B6 | 7.72:1 on bg, 6.31:1 on surface-alt |
| accent | #5EEAD4 | 12.78:1 on bg. Use dark text `#04201C` on it, 11.56:1 |
| accent-hover | #99F6E4 | lighter on hover in dark mode |
| company | #C4B5FD | 10.24:1 on bg |
| job | #7DD3FC | 11.34:1 on bg |
| person | #FCD34D | 13.12:1 on bg |
| pinned | #FBBF24 | 11.33:1 on bg |
| applied | #86EFAC | 13.47:1 on bg |
| connected | #93C5FD | 10.49:1 on bg |

Dark-mode advice: pill fills are the category colour at about 14% over the surface with the full colour as text. Elevation comes from lighter surfaces, not shadows. Avoid pure white text (use the listed `text`).

### E. "Sage" (light, calm and natural)
Mood: soothing, growth-oriented, quietly premium. Green-tinted neutrals and a forest green primary. A good alternative if the user does not want blue or orange.

| Token | Hex | Notes |
|---|---|---|
| bg | #F5F7F2 | |
| surface | #FFFFFF | |
| surface-alt | #E9EEE3 | |
| border | #D6DECD | decorative; inputs #8C9A8E |
| text | #1F2A22 | 13.78:1 on bg |
| text-2 | #5A6B5E | 5.26:1 on bg, 4.81:1 on surface-alt |
| accent | #2F6B4F | white on it 6.29:1 |
| accent-hover | #245640 | |
| company | #6B4E9B | 6.11:1 on bg |
| job | #0E6B7A | 5.72:1 on bg (teal, distinct from the green accent) |
| person | #9A5B13 | 5.02:1 on bg |
| pinned | #8A6A00 | 4.70:1 on bg |
| applied | #166534 | 6.61:1 on bg |
| connected | #1F5F8B | 6.35:1 on bg |

Note: green is both the brand and the "applied" status here. That is acceptable because applied is a success state, but use a check icon so the pill is not mistaken for the brand colour.

---

## 3. Typography

### 3.1 Font pairings (all on Google Fonts)
| Pairing | Heading | Body | Fits |
|---|---|---|---|
| 1. Modern neutral | Inter Tight (or Inter) | Inter | Harbor, Midnight. Safe, very legible, tabular numbers for counts. |
| 2. Warm editorial | Fraunces (variable, soft, optical size on) | Source Sans 3 | Linen, Sage. Serif headings give personality. |
| 3. Friendly geometric | Plus Jakarta Sans | Plus Jakarta Sans (or DM Sans) | Pop. Rounded and confident. |
| 4. Technical | Space Grotesk | IBM Plex Sans | Midnight. Tool-like feel. |
| 5. Humanist | Manrope | Public Sans | Harbor or Sage. Clean, slightly warmer than Inter. |

Use `font-feature-settings: "tnum"` (tabular numbers) for counts and match scores. Load at most two families and subset to the weights you use.

### 3.2 Type scale (1.25 ratio, base 16 px)
| Role | Size | Line height | Weight | Notes |
|---|---|---|---|---|
| h1 (page or search title) | 28 px / 1.75 rem | 1.2 | 700 | Once per page |
| h2 (section, such as "Jobs") | 20 px / 1.25 rem | 1.3 | 650 to 700 | Section header with count |
| h3 (item name) | 16 px / 1 rem | 1.35 | 600 | The main scan target |
| body | 15 px / 0.9375 rem (16 px on mobile) | 1.55 | 400 | Alignment text, max 65 ch wide |
| small / meta | 13 px / 0.8125 rem | 1.45 | 400 to 500 | Location, company, date |
| caption / pill | 12 px / 0.75 rem | 1.3 | 600 | Pills, tab counts; uppercase with 0.04 em tracking only for pills |

Rules: do not go below 12 px. Bold only the item name and key phrases. Differentiate hierarchy with size, weight and tone together, not colour alone. Cap long text blocks at about 65 characters per line.

---

## 4. Results-page information architecture: patterns and trade-offs

| Pattern | Pros | Cons | Fit |
|---|---|---|---|
| Tabs per entity type | Clear mental model, cuts the page to one list at a time, matches NN/g guidance for desktop and small tab sets | Hides relations between types; cannot compare across tabs; counts needed so nothing feels missing | High. A strong default. |
| Accordion sections | Everything on one page, good on mobile, easy to show counts | Collapsed state looks empty on desktop; long scroll when open | Medium (mobile fallback for tabs) |
| Master-detail split view | Fast review without losing place (LinkedIn Jobs style), room for the full alignment note and connect message | Needs width; awkward on mobile (becomes list then page) | High for review-heavy use |
| Card grid with expandable cards | Visual, friendly, shows the alignment summary on each card | Harder to scan and compare than rows; expanding shifts layout | Medium |
| Kanban pipeline | Matches the Huntr or Teal workflow and makes status visible | Needs status as the main axis; the first view of results is not yet a pipeline; empty columns early on | Medium for a second view ("Tracker"), low for the first view |
| Grouped by company (company, its jobs, its people) | Mirrors how networking works (find a person at the company where there is an opening); shows relations | Hierarchy is deep (company, then items), so keep to two levels; companies with no jobs or people look odd | High and distinctive |
| Sticky summary header with counts | Constant orientation, quick jump, shows progress (for example "4 of 12 jobs applied") | Takes vertical space; keep it to one row | High (add to any pattern) |
| Filter and sort chips | Fast narrowing (Pinned, Not applied, Strong fit) without a settings page | Too many chips cause clutter; keep 4 to 6 | High |
| "Show more" truncation of alignment notes | Directly fixes the information dump; two to three lines clamped with "Read why it fits" | Hidden text may be missed; the first line must be the best one | High |
| Side drawer for details | Keeps context, good for connect message generation and long notes | Third level risk if a drawer opens another panel; modal focus management needed | Medium to high (use instead of master-detail on narrower screens) |

Combinations that work for this product:
1. Sticky summary bar, then tabs, then dense rows with truncated alignment notes, then a side drawer for details and the connect message.
2. Grouped-by-company outline with a "Group by" switch (Company or Type).
3. Master-detail with tabs above the list.

Also consider a "Top picks" band of three cards above the tabs to give the page a clear first answer ("Start here"), which supports information scent and reduces the dump.

---

## 5. Micro-interactions and affordances

### Items and actions
- Row hover: raise to surface-alt, reveal the pin, copy and "Open" actions on the right (always visible on touch). Do not move the layout.
- Pin: a bookmark or star icon with a quick fill animation (150 ms scale 1.0 to 1.2 to 1.0) and a toast with Undo. Pinned items get a thin pinned-colour left stripe.
- Status pills: use a single click-to-cycle or a small menu. For jobs: "Not applied", then "Applied". For people: "Not contacted", "Message ready" and "Connected". Each pill has an icon (check, paper-plane, link), a label and a colour, so it never relies on colour alone. Applied items dim slightly (text-2) so remaining work stands out.
- Category identity: a small coloured icon chip (building for company, briefcase for job, person for people) at the left of each row, in the category colour.
- Alignment note: a two-line clamp with a fade, a "Why it fits" link, and optional tagged chips (for example "Skills match", "Location", "Seniority") that give scent before expanding. Optional match strength as a three-dot meter rather than a percentage the agent cannot justify.
- Connect message: generate in the drawer, with a visible text area, "Copy" (with a "Copied" state), "Regenerate" and "Mark as connected". Offer tone chips (Short, Warm, Direct).
- Keyboard: j and k to move between rows, p to pin, Enter to open. Show hints in tooltips (Linear style).

### Agent running in the background
- Show a progress card at the top of the results page rather than a spinner: a stepper with stages ("Understanding your profile", "Finding companies", "Finding jobs", "Finding people", "Writing why-it-fits notes"), the current stage highlighted, a determinate bar where possible, and an elapsed time.
- Stream results in. Show each tab count increasing live ("Companies 7") with a subtle pulse, so the page is useful before it finishes. Skeleton rows for items still coming.
- Show "You can leave this page. We'll keep searching" with a Cancel button, matching the existing background-search behaviour. Surface running searches in Previous Searches with a small animated dot and a status ("Running 3 of 5 steps").
- Completed and failed states: a toast and a badge on the previous-search item. A failed or cancelled search shows what was found so far and a "Resume" or "Retry" action.
- Respect `prefers-reduced-motion`: replace pulses and shimmer with static indicators.

### Empty and zero states
- First visit: a short, friendly empty state with one example search ("Product designer, Seattle, fintech") that fills the form on click. Avoid a blank page.
- No results in a tab: say why and what to do ("No open jobs found for these companies. Try widening location") with a single action.
- No pins yet: a hint with the pin icon ("Pin items to build your shortlist").
- Filtered to zero: show the active filters with a "Clear filters" button.

### Feedback and polish
- Use consistent 150 to 200 ms ease-out transitions. Use the accent only for the primary action per view (one primary button).
- Visible focus rings (2 px accent at 3:1 or more against the surface). Minimum 40 px touch targets on mobile.
- Subtle count badges on tabs, and a sticky header that shrinks on scroll.

---

## 6. Recommended design directions for mockup designers

Each direction below differs on palette, IA and typography so the mockups are genuinely comparable.

### Direction 1: "Field Notes" (editorial, warm)
Concept: the results page reads like a well-edited briefing from a thoughtful friend. A short headline sentence at the top summarises the search ("We found 8 companies, 12 jobs and 9 people near you"), then a "Start here" band shows the three best moves. Below it, sections are separated by generous space and serif headings, and each item is a clean row with a one-line reason. The warm cream palette lowers the stress of job hunting.
- Palette: A. Linen.
- IA: sticky summary header, then accordion-style sections on one scrolling page, each with a clamped alignment note and "Why it fits" expand-in-place.
- Typography: Fraunces for h1 and h2, Source Sans 3 for body. Larger h2 (22 px), relaxed density.

### Direction 2: "Command Center" (dense pro tool)
Concept: a Linear-style workspace for power users who run many searches. Left sidebar with Previous Searches (with running indicators), a centre list of dense 36 px rows, and a persistent right pane showing the selected item's alignment, evidence and connect message. Keyboard-first with a command palette and a Compact or Comfortable toggle. Dark by default with a light option.
- Palette: D. Midnight (with Harbor as the light variant).
- IA: master-detail split view with tabs above the list, filter chips, sticky counts.
- Typography: Space Grotesk headings, IBM Plex Sans body, tabular numerals, 13 px list text.

### Direction 3: "Pipeline" (kanban tracker)
Concept: treat results as a job-hunt funnel from day one, in the spirit of Huntr and Teal. After a search finishes, items arrive in a "New" column. The user pins them to "Shortlist", then moves them through "Applied" or "Connected", then "Following up". Companies sit in a swim lane header with their jobs and people as cards beneath. A toggle switches to a plain list for those who prefer it. Strong status colour and progress count in the header ("5 of 12 actions done").
- Palette: C. Pop (vibrant status colours, butter-yellow highlights).
- IA: kanban board with swim lanes by company, drawer for details, sticky progress header.
- Typography: Plus Jakarta Sans throughout, bold 16 px card titles, 12 px pill captions.

### Direction 4: "Company Map" (relationship-first)
Concept: the unit of the page is the company, because networking is about getting from a person to an opening. Each company is an expandable panel showing its fit summary, then its open jobs and the people to contact there, side by side. A "Group by: Company | Type" switch lets users fall back to flat lists. Cross-links ("Message Priya about the Data Analyst role") add information scent and make the connect action obvious.
- Palette: B. Harbor (cool, professional) with violet for companies.
- IA: grouped-by-company two-level outline, with a side drawer for the connect message and filter chips for "Has open job", "Has contact".
- Typography: Manrope headings, Public Sans body, 20 px company names.

### Direction 5: "Calm Focus" (guided, low-density)
Concept: for overwhelmed users. Show one tab at a time with large cards, three to five items per view, and a "Show 5 more" button, instead of full lists. A progress ring tracks pinned and completed actions. The agent's progress display is prominent and friendly while it works. Large type, soft sage colours, and gentle motion.
- Palette: E. Sage.
- IA: tabs per entity type with a card grid (2 columns), expandable cards that open a details drawer, "Top picks" band, and a progress ring in the sticky header.
- Typography: Inter Tight headings with Inter body at 16 px, generous line height, 24 px h2.

---

## Implementation notes (for later, not for the mockups)
- Define colours as CSS variables in Tailwind v4 `@theme` (for example `--color-bg`, `--color-accent`) so palettes and dark mode swap without touching components.
- Build a 12-step ramp per hue if a full system is wanted (Radix or Tailwind 50 to 950), and map tokens to ramp steps rather than raw hex.
- Verify every final pill, hover and disabled state for AA after the real tints are chosen. The ratios above cover the base pairs only.
