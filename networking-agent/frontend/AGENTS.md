# Map · Linen design rules

The UI follows the owner-approved **Map · Linen** design
([`docs/ui_drafts_v2/04-map-linen/`](../../docs/ui_drafts_v2/04-map-linen/README.md); port plan in
[`docs/map-linen-ui/plan.md`](../docs/map-linen-ui/plan.md)). React + plain CSS: no Tailwind, no
component library. These rules apply whenever you write UI code.

## Styles live in `src/styles/linen.css`

- Tokens are CSS variables on `:root[data-theme=light|dark]` (`--bg`, `--surface`, `--alt`,
  `--border`, `--text`, `--text2`, `--accent`, entity colours `--co` / `--job` / `--per` /
  `--pin` / `--app` / `--con` with `-d` (text on tint) and `-t` (tint) steps, `--danger`).
- Components use `var(--token)` only. **Never write a hex or rgb colour outside the token
  blocks**; if a colour is missing, add a token to both themes.
- Reuse the existing classes before adding new ones: `.btn` (`.pri`, `.sm`, `.xs`, `.ghost`,
  `.danger`), `.ibtn`, `.pill.*`, `.chip`, `.status.app|.con`, `.card`, `.co-panel`, `.pane`,
  `.row`, `.note`, `.disc`, `.xlink`, `.drawer`, `.toast`, `.alert`. New classes go at the end
  of `linen.css`; avoid inline `style` except for computed values (e.g. a fit bar width).
- Light is the default. The theme toggle sets `data-theme` on `<html>` and saves it in
  `localStorage` (`na-theme`); `index.html` applies it before first paint.
- Breakpoints: 1180px (index becomes chips, search rail stacks), 980px (sidebar becomes a
  drawer), 720px (compact).

## Typography

- Fraunces (`var(--head)`, self-hosted via `@fontsource-variable/fraunces`) for headings, company
  names and row titles; Source Sans 3 (`var(--ui)`) for everything else.
- Scale: body 16, meta 13.5–14, h1 24, company name 20, row title 15.5.

## Components and mechanics

- Icons: `<Icon name="…" />` from `@/components/icon` (the draft's stroke icon set). Icons are
  decorative (`aria-hidden`); label the control instead. Add new icons to its `PATHS` map.
- Merge classes with `cx()` from `@/utils/cx`.
- Use native, labelled form controls (`<input>`, `<textarea>`, `<select>`, checkbox with
  `role="switch"`), each with a visible `<label>` or an `aria-label`.
- Toggles expose `aria-pressed`; disclosures expose `aria-expanded` / `aria-controls`.
- Toasts: `useToast()` from `@/utils/use-toast` (offer Undo for reversible actions like pins).
- Text must meet WCAG AA in both themes, including inactive toggles and chips.
- Keep non-component exports (helpers, constants, hooks) in `src/utils/` so component files only
  export components (fast refresh).
