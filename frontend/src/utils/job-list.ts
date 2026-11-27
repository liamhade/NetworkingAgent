import type { CompanyResult, JobResult, PinMap, StatusMap } from '@/api'

/** "Strong fit" filter threshold (job score). */
export const STRONG_FIT = 75

export type Filter = 'strong' | 'hasPeople' | 'notApplied' | 'pinned'
export type SortId = 'fit' | 'pinned' | 'experience' | 'name'

/** One job in the flattened list, with the company it belongs to. */
export interface JobEntry {
  /** Unique within the list, stable while the results are the same. */
  id: string
  job: JobResult
  company: CompanyResult
  /** Identity of the company (its key, or its name when unkeyed). */
  companyId: string
  /** Position in Best-fit order, 1 = best. */
  position: number
}

export const companyId = (company: CompanyResult) => company.key || company.name

/**
 * Every job of every company as one list in Best-fit order: the ranker's `rank` when
 * present, otherwise (searches saved before ranking) job score descending, then company
 * order, then job order.
 */
export function rankJobs(companies: CompanyResult[]): JobEntry[] {
  const flat = companies.flatMap((company, companyIndex) =>
    company.jobs.map((job, jobIndex) => ({ job, company, companyIndex, jobIndex })),
  )
  return flat
    .toSorted(
      (a, b) =>
        (a.job.rank ?? Infinity) - (b.job.rank ?? Infinity) ||
        (b.job.score ?? -1) - (a.job.score ?? -1) ||
        a.companyIndex - b.companyIndex ||
        a.jobIndex - b.jobIndex,
    )
    .map(({ job, company, companyIndex, jobIndex }, index) => ({
      id: `job-${companyIndex}-${jobIndex}`,
      job,
      company,
      companyId: companyId(company),
      position: index + 1,
    }))
}

/** The smallest number of years a posting asks for ("3-5 years" is 3); null when unknown. */
export function minYears(text: string | null | undefined): number | null {
  const match = text?.match(/\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

export interface View {
  filters: ReadonlySet<Filter>
  /** Selected companies (by `companyId`); empty means every company. */
  companies: ReadonlySet<string>
  sort: SortId
}

export interface Marks {
  statuses: StatusMap
  pins: PinMap
}

export const isJobPinned = ({ pins }: Marks, entry: JobEntry) =>
  !!entry.job.key && !!pins.job[entry.job.key]

/** Entries that pass the filters, in the chosen sort order. */
export function applyView(entries: JobEntry[], view: View, marks: Marks): JobEntry[] {
  const { filters, companies, sort } = view
  const kept = entries.filter((entry) => {
    if (companies.size > 0 && !companies.has(entry.companyId)) return false
    if (filters.has('strong') && (entry.job.score ?? 0) < STRONG_FIT) return false
    if (filters.has('hasPeople') && entry.company.people.length === 0) return false
    if (filters.has('notApplied') && marks.statuses.job[entry.job.key]) return false
    if (filters.has('pinned') && !isJobPinned(marks, entry)) return false
    return true
  })
  const byPosition = (a: JobEntry, b: JobEntry) => a.position - b.position
  return kept.toSorted((a, b) => {
    switch (sort) {
      case 'pinned':
        return Number(isJobPinned(marks, b)) - Number(isJobPinned(marks, a)) || byPosition(a, b)
      case 'experience': {
        const years = (entry: JobEntry) => minYears(entry.job.years_required) ?? Infinity
        const [ya, yb] = [years(a), years(b)]
        return (ya === yb ? 0 : ya < yb ? -1 : 1) || byPosition(a, b)
      }
      case 'name':
        return a.company.name.localeCompare(b.company.name) || byPosition(a, b)
      default:
        return byPosition(a, b)
    }
  })
}

export interface CompanyCount {
  id: string
  company: CompanyResult
  jobs: number
}

/** The companies that have jobs in the list, in order of their best job, with job counts. */
export function companyCounts(entries: JobEntry[]): CompanyCount[] {
  const counts = new Map<string, CompanyCount>()
  for (const { companyId, company } of entries) {
    const found = counts.get(companyId)
    if (found) found.jobs += 1
    else counts.set(companyId, { id: companyId, company, jobs: 1 })
  }
  return [...counts.values()]
}

export interface Totals {
  jobs: number
  companies: number
  contacts: number
  applied: number
  connected: number
  pinned: number
}

/** Totals across the whole search, for the stats strip. */
export function totals(companies: CompanyResult[], { statuses, pins }: Marks): Totals {
  const jobs = companies.flatMap((company) => company.jobs)
  const people = companies.flatMap((company) => company.people)
  return {
    jobs: jobs.length,
    companies: companies.length,
    contacts: people.length,
    applied: jobs.filter((job) => statuses.job[job.key]).length,
    connected: people.filter((person) => statuses.person[person.key]).length,
    pinned:
      companies.filter((company) => company.key && pins.company[company.key]).length +
      jobs.filter((job) => pins.job[job.key]).length +
      people.filter((person) => pins.person[person.key]).length,
  }
}
