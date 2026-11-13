import { useEffect, useState } from 'react'
import { RiBriefcaseLine, RiBuilding2Line, RiUserLine } from '@remixicon/react'
import { withRetry } from '@/utils/retry'
import {
  listEntities,
  type CompanyEntity,
  type EntityKind,
  type EntityMap,
  type JobEntity,
  type PersonEntity,
  type Sighting,
  type StatusKind,
  type StatusMap,
} from '@/api'
import { AlignmentBox } from '@/components/alignment-box'
import { Chip } from '@/components/base/badges/chip'
import { Spinner } from '@/components/base/spinner/spinner'
import { StatusToggle } from '@/components/status-toggle'
import { ErrorBanner, ExternalLink } from '@/pages/results'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'

type ToggleStatus = (kind: StatusKind, key: string, active: boolean) => void

/** Searches listed on a card before collapsing the rest into "+N more". */
const MAX_SEARCH_LINKS = 3

const PAGES = {
  companies: {
    title: 'Companies',
    blurb: 'Every company that has come up in your searches.',
    icon: RiBuilding2Line,
    noun: ['company', 'companies'],
  },
  jobs: {
    title: 'Jobs',
    blurb: 'Every job opening that has come up in your searches.',
    icon: RiBriefcaseLine,
    noun: ['job', 'jobs'],
  },
  people: {
    title: 'People',
    blurb: 'Everyone suggested to connect with across your searches.',
    icon: RiUserLine,
    noun: ['person', 'people'],
  },
} as const

/**
 * Loads one entity list. Re-fetches when `refreshKey` changes (bumped by the app whenever a
 * new search is saved); the previous list stays on screen while the new one loads.
 */
function useEntities<K extends EntityKind>(kind: K, refreshKey: number) {
  const [items, setItems] = useState<EntityMap[K][] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    withRetry((signal) => listEntities(kind, signal), controller.signal)
      .then((loaded) => {
        setItems(loaded)
        setError(null)
      })
      .catch((caught: Error) => {
        if (controller.signal.aborted) return
        console.error(caught)
        setError(`Could not load your ${PAGES[kind].title.toLowerCase()}.`)
      })
    return () => controller.abort()
  }, [kind, refreshKey])

  return { items, error }
}

interface PageProps {
  refreshKey: number
  onOpenSearch: (id: string) => void
}

interface ToggleProps {
  entityStatuses: StatusMap
  statusError: string | null
  onToggleStatus: ToggleStatus
}

export function CompaniesPage({ refreshKey, onOpenSearch }: PageProps) {
  const { items, error } = useEntities('companies', refreshKey)
  return (
    <EntityPage kind="companies" items={items} error={error}>
      {(company) => <CompanyCard company={company} onOpenSearch={onOpenSearch} />}
    </EntityPage>
  )
}

export function JobsPage({
  refreshKey,
  onOpenSearch,
  entityStatuses,
  statusError,
  onToggleStatus,
}: PageProps & ToggleProps) {
  const { items, error } = useEntities('jobs', refreshKey)
  return (
    <EntityPage kind="jobs" items={items} error={error} statusError={statusError}>
      {(job) => (
        <JobCard
          job={job}
          applied={entityStatuses.job[job.key] ?? false}
          onToggle={(active) => onToggleStatus('job', job.key, active)}
          onOpenSearch={onOpenSearch}
        />
      )}
    </EntityPage>
  )
}

export function PeoplePage({
  refreshKey,
  onOpenSearch,
  entityStatuses,
  statusError,
  onToggleStatus,
}: PageProps & ToggleProps) {
  const { items, error } = useEntities('people', refreshKey)
  return (
    <EntityPage kind="people" items={items} error={error} statusError={statusError}>
      {(person) => (
        <PersonCard
          person={person}
          connected={entityStatuses.person[person.key] ?? false}
          onToggle={(active) => onToggleStatus('person', person.key, active)}
          onOpenSearch={onOpenSearch}
        />
      )}
    </EntityPage>
  )
}

interface EntityPageProps<K extends EntityKind> {
  kind: K
  items: EntityMap[K][] | null
  error: string | null
  statusError?: string | null
  children: (item: EntityMap[K]) => React.ReactNode
}

function EntityPage<K extends EntityKind>({
  kind,
  items,
  error,
  statusError,
  children,
}: EntityPageProps<K>) {
  const page = PAGES[kind]
  const Icon = page.icon
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <h1 className="text-title-1-semibold text-text-primary">{page.title}</h1>
          {items && items.length > 0 && (
            <Chip variant="caption" color="soft">
              {items.length} {items.length === 1 ? page.noun[0] : page.noun[1]}
            </Chip>
          )}
        </div>
        <p className="text-body-regular text-text-secondary">{page.blurb}</p>
      </header>

      {error && <ErrorBanner message={error} />}
      {statusError && <ErrorBanner message={statusError} />}

      {items === null ? (
        !error && (
          <div className="flex items-center gap-2 text-body-regular text-text-tertiary">
            <Spinner />
            Loading…
          </div>
        )
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-3xl border border-dashed border-border-button-default px-6 py-10 text-center">
          <Icon aria-hidden className="size-6 text-foreground-icon-tertiary" />
          <p className="text-body-regular text-text-secondary">
            No {page.noun[1]} yet. Run a search and they'll show up here.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          {items.map((item) => (
            <li key={item.key}>{children(item)}</li>
          ))}
        </ul>
      )}
    </main>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <article className="flex flex-col gap-3 rounded-3xl border border-border-button-default bg-background-primary-default p-5">
      {children}
    </article>
  )
}

function CardIcon({ icon: Icon }: { icon: typeof RiUserLine }) {
  return (
    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-background-secondary-default text-foreground-icon-secondary">
      <Icon aria-hidden className="size-5" />
    </span>
  )
}

/** When the entity was last seen and links back to the searches it came from. */
function SeenIn({
  sighting,
  onOpenSearch,
}: {
  sighting: Sighting
  onOpenSearch: (id: string) => void
}) {
  const lastSeen = new Date(sighting.last_seen)
  const shown = sighting.searches.slice(0, MAX_SEARCH_LINKS)
  const hidden = sighting.searches.slice(MAX_SEARCH_LINKS)
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-separator-border pt-3 text-caption-1-medium text-text-tertiary">
      <span>
        Last seen{' '}
        <time dateTime={sighting.last_seen} title={fullDateFormat.format(lastSeen)}>
          {formatRelativeDate(lastSeen)}
        </time>
        {' · '}
        {sighting.searches.length === 1 ? 'in' : `in ${sighting.searches.length} searches:`}
      </span>
      {shown.map((search) => (
        <button
          key={search.id}
          type="button"
          onClick={() => onOpenSearch(search.id)}
          title={`Open “${search.title}”`}
          className="max-w-56 cursor-pointer truncate rounded-md bg-background-secondary-default px-1.5 py-0.5 text-caption-1-medium text-text-secondary outline-none hover:bg-background-secondary-hover hover:text-text-primary focus-visible:ring-2 focus-visible:ring-border-focus-ring"
        >
          {search.title}
        </button>
      ))}
      {hidden.length > 0 && (
        <span title={hidden.map((search) => search.title).join('\n')}>
          +{hidden.length} more
        </span>
      )}
    </div>
  )
}

function CompanyCard({
  company,
  onOpenSearch,
}: {
  company: CompanyEntity
  onOpenSearch: (id: string) => void
}) {
  return (
    <Card>
      <div className="flex items-start gap-3">
        <CardIcon icon={RiBuilding2Line} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h2 className="text-title-3-semibold text-text-primary">
            <ExternalLink href={company.url}>{company.name}</ExternalLink>
          </h2>
          {company.description && (
            <p className="text-body-2-regular text-text-secondary">{company.description}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-1">
          <Chip variant="caption" color="soft">
            {company.job_count} {company.job_count === 1 ? 'job' : 'jobs'}
          </Chip>
          <Chip variant="caption" color="soft">
            {company.person_count} {company.person_count === 1 ? 'contact' : 'contacts'}
          </Chip>
        </div>
      </div>
      <AlignmentBox text={company.alignment} />
      <SeenIn sighting={company} onOpenSearch={onOpenSearch} />
    </Card>
  )
}

function JobCard({
  job,
  applied,
  onToggle,
  onOpenSearch,
}: {
  job: JobEntity
  applied: boolean
  onToggle: (active: boolean) => void
  onOpenSearch: (id: string) => void
}) {
  const meta = [job.company, job.location, job.salary].filter(Boolean).join(' · ')
  return (
    <Card>
      <div className="flex items-start gap-3">
        <CardIcon icon={RiBriefcaseLine} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h2 className="text-body-medium text-text-primary">
            <ExternalLink href={job.url}>{job.title}</ExternalLink>
          </h2>
          {meta && <p className="text-body-2-regular text-text-tertiary">{meta}</p>}
        </div>
        <StatusToggle kind="job" isSelected={applied} onChange={onToggle} />
      </div>
      <AlignmentBox text={job.alignment} />
      <SeenIn sighting={job} onOpenSearch={onOpenSearch} />
    </Card>
  )
}

function PersonCard({
  person,
  connected,
  onToggle,
  onOpenSearch,
}: {
  person: PersonEntity
  connected: boolean
  onToggle: (active: boolean) => void
  onOpenSearch: (id: string) => void
}) {
  const meta = [person.title, person.company].filter(Boolean).join(' · ')
  return (
    <Card>
      <div className="flex items-start gap-3">
        <CardIcon icon={RiUserLine} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <h2 className="text-body-medium text-text-primary">
            <ExternalLink href={person.profile_url}>{person.name}</ExternalLink>
          </h2>
          {meta && <p className="text-body-2-regular text-text-tertiary">{meta}</p>}
        </div>
        <StatusToggle kind="person" isSelected={connected} onChange={onToggle} />
      </div>
      <AlignmentBox text={person.alignment} label="Why connect" />
      <SeenIn sighting={person} onOpenSearch={onOpenSearch} />
    </Card>
  )
}
