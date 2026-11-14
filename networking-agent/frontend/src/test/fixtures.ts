import type { CompanyEntity, JobEntity, PersonEntity, PinMap, StatusMap } from '@/api'

/** Test data builders for the entity pages and sort helpers. */

const DAY = 24 * 60 * 60 * 1000
const BASE = Date.parse('2026-01-31T12:00:00Z')

/** ISO timestamp `daysAgo` days before a fixed base date. */
export const seenDaysAgo = (daysAgo: number) => new Date(BASE - daysAgo * DAY).toISOString()

const sighting = (key: string, daysAgo: number) => ({
  key,
  first_seen: seenDaysAgo(daysAgo + 1),
  last_seen: seenDaysAgo(daysAgo),
  searches: [{ id: 's1', title: 'Search one', created_at: seenDaysAgo(daysAgo), status: 'done' as const }],
})

const slug = (text: string) => text.toLowerCase().replaceAll(' ', '-')

export function company(name: string, daysAgo: number, extra: Partial<CompanyEntity> = {}) {
  return {
    ...sighting(`company:${slug(name)}`, daysAgo),
    name,
    url: `https://${slug(name)}.example`,
    description: '',
    alignment: '',
    job_count: 0,
    person_count: 0,
    ...extra,
  } satisfies CompanyEntity
}

export function job(title: string, daysAgo: number, extra: Partial<JobEntity> = {}) {
  return {
    ...sighting(`job:${slug(title)}`, daysAgo),
    title,
    url: `https://jobs.example/${slug(title)}`,
    location: '',
    salary: '',
    alignment: '',
    company: 'Acme',
    company_key: 'company:acme',
    ...extra,
  } satisfies JobEntity
}

export function person(name: string, daysAgo: number, extra: Partial<PersonEntity> = {}) {
  return {
    ...sighting(`person:${slug(name)}`, daysAgo),
    name,
    title: '',
    profile_url: `https://linkedin.example/${slug(name)}`,
    alignment: '',
    company: 'Acme',
    company_key: 'company:acme',
    ...extra,
  } satisfies PersonEntity
}

export const emptyPins = (): PinMap => ({ company: {}, job: {}, person: {} })
export const emptyStatuses = (): StatusMap => ({ job: {}, person: {} })
