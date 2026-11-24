import type { EntityKind } from '@/api'

/** An entity another card links to: where to go (`kind` + `key`) and what to call it. */
export interface RelatedEntity {
  kind: EntityKind
  key: string
  label: string
  /** Secondary text (a person's role, a job's location). */
  detail?: string
}

/** Where to take the user: the page of `kind`, scrolled to the card with this `key`. */
export interface Focus {
  kind: EntityKind
  key: string
}

/** Jobs and people belong to a company; that link is the only relation the saved data has. */
interface OfCompany {
  key: string
  company_key: string
}

/** Groups entities by the company they belong to, keeping list order. */
export function groupByCompany<T extends OfCompany>(items: readonly T[] | null) {
  const groups = new Map<string, T[]>()
  for (const item of items ?? []) {
    const group = groups.get(item.company_key)
    if (group) group.push(item)
    else groups.set(item.company_key, [item])
  }
  return groups
}

export const jobRelation = (job: {
  key: string
  title: string
  location: string
}): RelatedEntity => ({ kind: 'jobs', key: job.key, label: job.title, detail: job.location })

export const personRelation = (person: {
  key: string
  name: string
  title: string
}): RelatedEntity => ({ kind: 'people', key: person.key, label: person.name, detail: person.title })

/** DOM id of an entity card, so a link can scroll to it. */
export const entityDomId = (key: string) => `entity-${key}`
