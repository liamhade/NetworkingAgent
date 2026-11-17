# v2 #3 Map · Split

Company Map's results page in the centre, Command Center's persistent detail pane on the right, Harbor palette, light by default. Open `results.html` (also `search.html`, `running.html`, `library.html`).

## What changed from v1, mapped to the feedback
| Owner feedback | Change |
|---|---|
| Liked Company Map results + colours | Kept collapsible company panels, jobs and people side by side, jump-to index, Group by Company/Type, filter chips, sort, cross-links ("Message Keniel about this role", "Role: ..."). Harbor colours kept. |
| Liked Command Center structure | Three columns: Previous Searches | results | detail pane. Clicking any company, job or person fills the pane (alignment note, Why connect, role picker, editable message with 300-char count and Copy, LinkedIn/posting links, Applied/Connected, pin). Replaces Company Map's drawer. |
| Light by default, with toggle | `data-theme` on `<html>`, set pre-paint from `localStorage['na-theme']`; toggle in the top bar. Dark is navy-tinted. |
| Company Map flaw: ~480px header | Header is now title + one stat/summary strip (about 70px); Start-here is a single pill; jump index sits in the sticky toolbar. First company starts at y=323 at 1440x900 (was ~480+). |
| WCAG AA both themes | Inactive Applied/Connected pills use full-contrast text and a 3:1 dashed border; chip/toggle labels checked. |

Layout: sidebar collapses to an icon rail (saved in `na-side`; default collapsed on results) so 64 + centre + 400px fits 1440. Below 1180px the pane is a right sheet; below 720px a bottom sheet (Esc/scrim/close; focus returns to the opener). Panels stack jobs/people via a container query when the centre is narrow.

## Palettes
| Token | Light | Dark |
|---|---|---|
| bg / surface / alt / border | #F4F7FB / #FFFFFF / #E8EEF6 / #D5DEEA | #0A1424 / #112038 / #1A2D4B / #27405F |
| text / text2 | #0F1E33 / #4B5C74 | #E8EFFA / #A7B8D0 |
| accent (links) / btn fill | #1D4ED8 / #1D4ED8 | #8DB0FF / #2D5FE3 |
| company fg / tint | #5B21B6 / #F1EBFD | #CBBBFF / #261E4A |
| job | #075985 / #E2F1FA | #8CCDF3 / #0F2D48 |
| person | #115E59 / #DDF3F0 | #7DDCCF / #0C3434 |
| pin | #92400E / #FDF1DC | #F7C06B / #36270D |
| applied | #166534 / #E1F5E7 | #7BD9A1 / #10331F |
| connected | #3730A3 / #E8E7FB | #B9B6FF / #232356 |
| danger | #B91C1C / #FDECEC | #FF8F8F / #3A1823 |

## Type scale (Manrope headings, Public Sans body)
Page title 22/800, banner 32/800, company 18/800, detail title 19/800, row title 14.5/700, body 14.5/400, meta 13/400, labels 12/700 caps.

## Implementation notes
- `theme.css` is token-first: every colour is a CSS variable (`--bg --surface --alt --border --input --text --text2 --accent --btn --co/-d/-t --job --per --pin --app --con --danger`), redefined under `[data-theme=dark]`. `-d` is the text colour on a `-t` tint; port as Tailwind theme tokens with a dark variant.
- Components: `.co-panel`, `.pane`, `.row` (+`.sel/.pinned/.done`), `.chip`, `.seg`, `.status` (Applied/Connected), `.ibtn.pin`, `.pill`, `.detail` (+`.d-head/.d-body/.d-foot`), `.tools` (sticky toolbar and jump index).
- All state (pins, applied, connected, selection, drafts) is keyed by entity id and re-rendered everywhere, matching the key-based state in the real app.
- Verified with Playwright: no console errors, no horizontal scroll at 1440 and 390, text contrast passes AA in both themes on all four pages.
