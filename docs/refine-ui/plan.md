# Refine the UI

TODO: "(refine UI) It's a little confusing at the moment, especially with the headers."

## Audit (before)

Checked in a browser at 1440px and 390px (Search, Companies, Jobs, People, Results) with mocked API data.

- Every page built its own header: Search used `.head` (h1 24px), Results the same plus breadcrumbs, Companies/Jobs/People `.lib-head` (h1 30px, different width: `wrap narrow`), so titles and left edges jumped between pages.
- Companies/Jobs/People showed the same four-way choice twice: the top nav and a second "Library type" segmented control.
- Count and Sort floated beside the title, away from the subtitle; no clear "controls at the right" pattern.
- Panel headings were a mix of Fraunces serif at 12px caps (sidebar, jump index) and 16-20px serif (rail, form), competing with the h1.
- The active nav item was only a light tint.
- Results had h1 followed directly by h3 company names (skipped h2).
- Empty states for the library pages had no next step.

## Changes

- New `components/page-header.tsx`: one header (optional crumbs, h1, subtitle/meta, right-aligned actions) used by Search, Results, Running, Companies, Jobs, People.
- Library pages: removed the duplicate type switcher, same `.wrap` width as other pages, count + Sort in the header actions, empty state has a "Start a search" button.
- Results: hidden h2 ("Companies" / "Results by type") so heading order is h1 > h2 > h3.
- `linen.css`: type scale (h1 28, panel title 15 UI font, eyebrow 12 caps, body 16), unified panel headings, nav active underline bar + bolder label, header divider, consistent page top padding, mobile header stacking. Removed the dead `.lib-head`/`.lib-tabs`/`.head` rules.
- No new tokens, colours, or dependencies; test IDs and roles kept (Sort combobox, h1, group roles).
