/**
 * Top-level pages, addressed by the URL hash (`#/jobs`) so back/forward and reload work.
 * `admin` is the owner's page; the app shows it only when `/api/me` says `is_admin`.
 */
export const VIEWS = ['search', 'companies', 'jobs', 'people', 'admin'] as const

export type View = (typeof VIEWS)[number]

/** URL hash for a view; the search view is `#/`. */
export const viewHash = (view: View) => (view === 'search' ? '#/' : `#/${view}`)

export function viewFromHash(hash: string): View {
  const name = hash.replace(/^#\/?/, '')
  return VIEWS.find((view) => view === name) ?? 'search'
}
