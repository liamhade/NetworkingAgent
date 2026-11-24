import type { Sighting } from '@/api'

/** How many of a page's entities are APPLIED / CONNECTED, out of how many listed. */
export interface StatusCount {
  active: number
  total: number
}

/**
 * Counts `items` whose status in `statuses` (one kind's slice of the status map) is on.
 * An entity with no saved status counts as not applied / connected, and statuses for
 * entities that are not in `items` are ignored, so `active <= total` always holds.
 */
export function countStatus(
  items: readonly Sighting[],
  statuses: Readonly<Record<string, boolean>>,
): StatusCount {
  const active = items.reduce((sum, item) => sum + Number(statuses[item.key] ?? false), 0)
  return { active, total: items.length }
}
