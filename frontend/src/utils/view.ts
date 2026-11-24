/** Top-level pages, addressed by the URL hash (`#/jobs`) so back/forward and reload work. */
export const VIEWS = ['search', 'companies', 'jobs', 'people'] as const

export type View = (typeof VIEWS)[number]

/** URL hash for a view; the search view is `#/`. */
export const viewHash = (view: View) => (view === 'search' ? '#/' : `#/${view}`)

export function viewFromHash(hash: string): View {
  const name = hash.replace(/^#\/?/, '')
  return VIEWS.find((view) => view === name) ?? 'search'
}
