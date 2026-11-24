import type { EntityKind, EntityMap, PinKind, PinMap, Sighting, StatusKind, StatusMap } from '@/api'

/**
 * Sort options for the Companies / Jobs / People pages. Pure functions (no React), so they
 * can be unit tested and reused if sorting ever moves server-side (the ids would become a
 * `?sort=` value).
 *
 * To add an option, add an entry to `SORT_OPTIONS` built from the comparator helpers
 * below; anything beyond the entity itself goes on `SortContext`.
 */

/** Per-user state a comparator may need beyond the entity's own fields. */
export interface SortContext {
  statuses: StatusMap
  pins: PinMap
}

export type Comparator<T> = (a: T, b: T, ctx: SortContext) => number

export interface SortOption<T> {
  id: string
  label: string
  compare: Comparator<T>
}

const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true })

/** Text A–Z, case/accent-insensitive; blank values go last. */
export function byText<T>(get: (item: T) => string): Comparator<T> {
  return (a, b) => {
    const left = get(a).trim()
    const right = get(b).trim()
    if (!left || !right) return Number(!left) - Number(!right)
    return collator.compare(left, right)
  }
}

/** Largest number first. */
export function byNumberDesc<T>(get: (item: T) => number): Comparator<T> {
  return (a, b) => get(b) - get(a)
}

/** Entities whose APPLIED / CONNECTED status equals `active` first. */
export function byStatus<T extends Sighting>(kind: StatusKind, active: boolean): Comparator<T> {
  return (a, b, ctx) => {
    const matches = (item: T) => (ctx.statuses[kind][item.key] ?? false) === active
    return Number(matches(b)) - Number(matches(a))
  }
}

/** Pinned entities first. */
export function byPinned<T extends Sighting>(kind: PinKind): Comparator<T> {
  return (a, b, ctx) => {
    const pinned = (item: T) => ctx.pins[kind][item.key] ?? false
    return Number(pinned(b)) - Number(pinned(a))
  }
}

/** Most recently seen first. */
export function byLastSeen<T extends Sighting>(): Comparator<T> {
  return (a, b) => Date.parse(b.last_seen) - Date.parse(a.last_seen)
}

const recent = { id: 'recent', label: 'Most recent', compare: byLastSeen() } as const

export const SORT_OPTIONS: { [K in EntityKind]: readonly SortOption<EntityMap[K]>[] } = {
  companies: [
    recent,
    { id: 'pinned', label: 'Pinned first', compare: byPinned('company') },
    { id: 'name', label: 'Name A–Z', compare: byText((c) => c.name) },
    { id: 'jobs', label: 'Most jobs', compare: byNumberDesc((c) => c.job_count) },
    { id: 'contacts', label: 'Most contacts', compare: byNumberDesc((c) => c.person_count) },
  ],
  jobs: [
    recent,
    { id: 'pinned', label: 'Pinned first', compare: byPinned('job') },
    { id: 'applied', label: 'Applied first', compare: byStatus('job', true) },
    { id: 'not-applied', label: 'Not applied first', compare: byStatus('job', false) },
    { id: 'title', label: 'Title A–Z', compare: byText((j) => j.title) },
    { id: 'company', label: 'Company A–Z', compare: byText((j) => j.company) },
  ],
  people: [
    recent,
    { id: 'pinned', label: 'Pinned first', compare: byPinned('person') },
    { id: 'connected', label: 'Connected first', compare: byStatus('person', true) },
    { id: 'not-connected', label: 'Not connected first', compare: byStatus('person', false) },
    { id: 'name', label: 'Name A–Z', compare: byText((p) => p.name) },
    { id: 'company', label: 'Company A–Z', compare: byText((p) => p.company) },
  ],
}

/** The server already returns lists most recently seen first. */
export const DEFAULT_SORT = recent.id

/**
 * Returns a new array sorted by option `sortId` (unknown ids fall back to the default).
 * The sort is stable and ties keep the incoming order, i.e. the server's recency order.
 */
export function sortEntities<K extends EntityKind>(
  kind: K,
  items: readonly EntityMap[K][],
  sortId: string,
  ctx: SortContext,
): EntityMap[K][] {
  const options: readonly SortOption<EntityMap[K]>[] = SORT_OPTIONS[kind]
  const option = options.find((o) => o.id === sortId) ?? options.find((o) => o.id === DEFAULT_SORT)
  if (!option) return [...items]
  return items.toSorted((a, b) => option.compare(a, b, ctx))
}
