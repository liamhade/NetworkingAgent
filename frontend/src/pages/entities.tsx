import { useEffect, useMemo, useState } from 'react'
import {
  listEntities,
  type CompanyEntity,
  type EntityKind,
  type EntityMap,
  type JobEntity,
  type PersonEntity,
  type PinKind,
  type PinMap,
  type Sighting,
  type StatusKind,
  type StatusMap,
} from '@/api'
import { Icon, type IconName } from '@/components/icon'
import { PinToggle } from '@/components/pin-toggle'
import { StatusToggle } from '@/components/status-toggle'
import { useToast } from '@/utils/use-toast'
import { ErrorBanner } from '@/pages/results'
import { countStatus, type StatusCount } from '@/utils/count-status'
import { cx } from '@/utils/cx'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'
import { initials } from '@/utils/initials'
import { withRetry } from '@/utils/retry'
import { DEFAULT_SORT, SORT_OPTIONS, sortEntities } from '@/utils/sort-entities'
import {
  entityDomId,
  groupByCompany,
  jobRelation,
  personRelation,
  type Focus,
  type RelatedEntity,
} from '@/utils/related'
import { viewHash } from '@/utils/view'

type ToggleStatus = (kind: StatusKind, key: string, active: boolean) => void
type TogglePin = (kind: PinKind, key: string, pinned: boolean) => void

/** Searches linked on a row before collapsing the rest into "+N more". */
const MAX_SEARCH_LINKS = 3

const PAGES = {
  companies: {
    title: 'Companies',
    blurb:
      'Every company the agent has surfaced across your searches. Open a search to see its jobs and people side by side.',
    icon: 'building',
    noun: ['company', 'companies'],
  },
  jobs: {
    title: 'Jobs',
    blurb: 'Every job opening from all your searches, with the company it belongs to.',
    icon: 'briefcase',
    noun: ['job', 'jobs'],
    /** Shown in the title pill as "X/Y applied". */
    statusLabel: 'applied',
  },
  people: {
    title: 'People',
    blurb: 'Everyone suggested to connect with across your searches, with their company and role.',
    icon: 'users',
    noun: ['person', 'people'],
    statusLabel: 'connected',
  },
} as const satisfies Record<EntityKind, { icon: IconName } & Record<string, unknown>>

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

/** Companies have no APPLIED / CONNECTED status, so their sort options never read one. */
const NO_STATUSES: StatusMap = { job: {}, person: {} }

/** The page's chosen sort and the list sorted by it (recomputed when a status/pin changes). */
function useSorted<K extends EntityKind>(
  kind: K,
  items: EntityMap[K][] | null,
  statuses: StatusMap,
  pins: PinMap,
) {
  const [sortId, setSortId] = useState<string>(DEFAULT_SORT)
  const sorted = useMemo(
    () => items && sortEntities(kind, items, sortId, { statuses, pins }),
    [kind, items, sortId, statuses, pins],
  )
  return { sorted, sort: { id: sortId, onChange: setSortId } }
}

/** "X of Y applied / connected" for the title pill; recomputed whenever a toggle flips. */
function useStatusCount(
  items: readonly Sighting[] | null,
  statuses: Readonly<Record<string, boolean>>,
) {
  return useMemo(() => items && countStatus(items, statuses), [items, statuses])
}

interface PageProps {
  refreshKey: number
  onOpenSearch: (id: string) => void
  /** Pinned companies / jobs / people for the current user, by entity key. */
  pins: PinMap
  pinError: string | null
  onTogglePin: TogglePin
  /** Card to scroll to and highlight once this page has loaded (set by a related-entity link). */
  focus: Focus | null
  onFocusHandled: () => void
  /** Jump to another entity's card on its own page. */
  onGoTo: (target: Focus) => void
}

interface ToggleProps {
  entityStatuses: StatusMap
  statusError: string | null
  onToggleStatus: ToggleStatus
}

/** Pin with an undo toast. */
function usePin(onTogglePin: TogglePin) {
  const toast = useToast()
  return (kind: PinKind, key: string, name: string, pinned: boolean) => {
    onTogglePin(kind, key, pinned)
    toast(`${pinned ? 'Pinned' : 'Unpinned'} ${name}`, () => onTogglePin(kind, key, !pinned))
  }
}

export function CompaniesPage({
  refreshKey,
  onOpenSearch,
  pins,
  pinError,
  onTogglePin,
  focus,
  onFocusHandled,
  onGoTo,
}: PageProps) {
  const { items, error } = useEntities('companies', refreshKey)
  const jobsByCompany = groupByCompany(useEntities('jobs', refreshKey).items)
  const peopleByCompany = groupByCompany(useEntities('people', refreshKey).items)
  const { sorted, sort } = useSorted('companies', items, NO_STATUSES, pins)
  const pin = usePin(onTogglePin)
  return (
    <EntityPage
      kind="companies"
      items={sorted}
      error={error}
      sort={sort}
      pinError={pinError}
      focus={focus}
      onFocusHandled={onFocusHandled}
    >
      {(company) => (
        <CompanyRow
          company={company}
          pinned={pins.company[company.key] ?? false}
          onTogglePin={(pinned) => pin('company', company.key, company.name, pinned)}
          onOpenSearch={onOpenSearch}
          jobs={(jobsByCompany.get(company.key) ?? []).map(jobRelation)}
          people={(peopleByCompany.get(company.key) ?? []).map(personRelation)}
          onGoTo={onGoTo}
        />
      )}
    </EntityPage>
  )
}

export function JobsPage({
  refreshKey,
  onOpenSearch,
  entityStatuses,
  statusError,
  onToggleStatus,
  pins,
  pinError,
  onTogglePin,
  focus,
  onFocusHandled,
  onGoTo,
}: PageProps & ToggleProps) {
  const { items, error } = useEntities('jobs', refreshKey)
  const peopleByCompany = groupByCompany(useEntities('people', refreshKey).items)
  const { sorted, sort } = useSorted('jobs', items, entityStatuses, pins)
  const statusCount = useStatusCount(items, entityStatuses.job)
  const pin = usePin(onTogglePin)
  return (
    <EntityPage
      kind="jobs"
      items={sorted}
      error={error}
      sort={sort}
      statusCount={statusCount}
      statusError={statusError}
      pinError={pinError}
      focus={focus}
      onFocusHandled={onFocusHandled}
    >
      {(job) => (
        <JobRow
          job={job}
          applied={entityStatuses.job[job.key] ?? false}
          onToggle={(active) => onToggleStatus('job', job.key, active)}
          pinned={pins.job[job.key] ?? false}
          onTogglePin={(pinned) => pin('job', job.key, job.title, pinned)}
          onOpenSearch={onOpenSearch}
          people={(peopleByCompany.get(job.company_key) ?? []).map(personRelation)}
          onGoTo={onGoTo}
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
  pins,
  pinError,
  onTogglePin,
  focus,
  onFocusHandled,
  onGoTo,
}: PageProps & ToggleProps) {
  const { items, error } = useEntities('people', refreshKey)
  const jobsByCompany = groupByCompany(useEntities('jobs', refreshKey).items)
  const { sorted, sort } = useSorted('people', items, entityStatuses, pins)
  const statusCount = useStatusCount(items, entityStatuses.person)
  const pin = usePin(onTogglePin)
  return (
    <EntityPage
      kind="people"
      items={sorted}
      error={error}
      sort={sort}
      statusCount={statusCount}
      statusError={statusError}
      pinError={pinError}
      focus={focus}
      onFocusHandled={onFocusHandled}
    >
      {(person) => (
        <PersonRow
          person={person}
          connected={entityStatuses.person[person.key] ?? false}
          onToggle={(active) => onToggleStatus('person', person.key, active)}
          pinned={pins.person[person.key] ?? false}
          onTogglePin={(pinned) => pin('person', person.key, person.name, pinned)}
          onOpenSearch={onOpenSearch}
          jobs={(jobsByCompany.get(person.company_key) ?? []).map(jobRelation)}
          onGoTo={onGoTo}
        />
      )}
    </EntityPage>
  )
}

/** How long a card stays highlighted after a related-entity link lands on it. */
const FOCUS_MS = 2500

/**
 * Scrolls to the card a related-entity link points at and returns its key while it is
 * highlighted (the app clears the focus after FOCUS_MS). Cards are never filtered out (only
 * re-sorted), so the target is in the list whatever the sort; if it is gone (e.g. its search
 * was deleted) nothing is highlighted.
 */
function useFocusCard(
  kind: EntityKind,
  items: readonly Sighting[] | null,
  focus: Focus | null,
  onHandled: () => void,
) {
  const active = focus?.kind === kind && items !== null
  const key = active ? focus.key : null
  useEffect(() => {
    if (!key) return
    document.getElementById(entityDomId(key))?.scrollIntoView?.({ block: 'center' })
    const timer = window.setTimeout(onHandled, FOCUS_MS)
    return () => window.clearTimeout(timer)
  }, [key, onHandled])
  return key !== null && items?.some((item) => item.key === key) ? key : null
}

interface EntityPageProps<K extends EntityKind> {
  kind: K
  items: EntityMap[K][] | null
  error: string | null
  sort: { id: string; onChange: (id: string) => void }
  /** Jobs / People: replaces the plain count pill with "X/Y applied" / "X/Y connected". */
  statusCount?: StatusCount | null
  statusError?: string | null
  pinError: string | null
  focus: Focus | null
  onFocusHandled: () => void
  children: (item: EntityMap[K]) => React.ReactNode
}

function EntityPage<K extends EntityKind>({
  kind,
  items,
  error,
  sort,
  statusCount,
  statusError,
  pinError,
  focus,
  onFocusHandled,
  children,
}: EntityPageProps<K>) {
  const page = PAGES[kind]
  const highlighted = useFocusCard(kind, items, focus, onFocusHandled)
  return (
    <div className="wrap narrow">
      <div className="lib-head">
        <h1>{page.title}</h1>
        {items && items.length > 0 && (
          <span className="pill neu num">
            {statusCount && 'statusLabel' in page
              ? `${statusCount.active}/${statusCount.total} ${page.statusLabel}`
              : `${items.length} ${items.length === 1 ? page.noun[0] : page.noun[1]}`}
          </span>
        )}
        <span className="sp" />
        {items && items.length > 1 && (
          <>
            <label className="tb-lab" htmlFor="lib-sort">
              Sort
            </label>
            <select
              id="lib-sort"
              className="auto"
              value={sort.id}
              onChange={(event) => sort.onChange(event.target.value)}
            >
              {SORT_OPTIONS[kind].map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </>
        )}
      </div>
      <p className="blurb">{page.blurb}</p>
      <div className="lib-tabs">
        <div className="seg" role="group" aria-label="Library type">
          {(Object.keys(PAGES) as EntityKind[]).map((target) => (
            <button
              key={target}
              type="button"
              aria-pressed={target === kind}
              onClick={() => (window.location.hash = viewHash(target))}
            >
              <Icon name={PAGES[target].icon} size="sm" />
              {PAGES[target].title}
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {statusError && <ErrorBanner message={statusError} />}
      {pinError && <ErrorBanner message={pinError} />}

      <div className="tcard">
        {items === null ? (
          !error && (
            <p className="loading">
              <span className="spin" aria-hidden="true" />
              Loading…
            </p>
          )
        ) : items.length === 0 ? (
          <div className="lib-empty">
            <Icon name={page.icon} size="lg" />
            <p>No {page.noun[1]} yet. Run a search and they will show up here.</p>
          </div>
        ) : (
          <ul className="rows" aria-label={page.title}>
            {items.map((item) => (
              <li
                key={item.key}
                id={entityDomId(item.key)}
                className={cx('row', item.key === highlighted && 'focused')}
              >
                {children(item)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function Title({ href, children, label }: { href: string; children: string; label: string }) {
  return (
    <h2 className="rhead">
      {href ? (
        <a className="rtitle" href={href} target="_blank" rel="noreferrer">
          {children}
          <Icon name="ext" />
          <span className="sr"> ({label})</span>
        </a>
      ) : (
        <span className="rtitle plain">{children}</span>
      )}
    </h2>
  )
}

function CompanyTag({ name }: { name: string }) {
  if (!name) return null
  return (
    <span className="cotag">
      <Icon name="building" />
      {name}
    </span>
  )
}

/** A toggled note under a row ("How you align", "Why connect", the LinkedIn message). */
function Note({
  label,
  text,
  variant,
  open,
  children,
}: {
  label: string
  text: string
  variant?: 'p'
  open: boolean
  children?: React.ReactNode
}) {
  return (
    <div className={cx('note', variant)} hidden={!open}>
      <div className="lab">{label}</div>
      <span className="msgnote">{text}</span>
      {children}
    </div>
  )
}

function Disclosure({
  label,
  open,
  onToggle,
}: {
  label: string
  open: boolean
  onToggle: () => void
}) {
  return (
    <button type="button" className="disc" aria-expanded={open} onClick={onToggle}>
      {label} <Icon name="chevron" />
    </button>
  )
}

/** When the entity was last seen, and links back to the searches it came from. */
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
    <div className="rmeta">
      <span>
        Last seen{' '}
        <time dateTime={sighting.last_seen} title={fullDateFormat.format(lastSeen)}>
          {formatRelativeDate(lastSeen)}
        </time>
      </span>
      <span>{sighting.searches.length === 1 ? 'in' : `in ${sighting.searches.length} searches:`}</span>
      {shown.map((search) => (
        <button
          key={search.id}
          type="button"
          className="pill neu seen-btn"
          onClick={() => onOpenSearch(search.id)}
          title={`Open “${search.title}”`}
        >
          {search.title}
        </button>
      ))}
      {hidden.length > 0 && (
        <span title={hidden.map((search) => search.title).join('\n')}>+{hidden.length} more</span>
      )}
    </div>
  )
}

/** Selectable chips for the entities connected to a card; renders nothing when there are none. */
function Related({
  label,
  items,
  onGoTo,
}: {
  label: string
  items: RelatedEntity[]
  onGoTo: (target: Focus) => void
}) {
  if (items.length === 0) return null
  const pill = items[0].kind === 'jobs' ? 'job' : 'per'
  return (
    <div className="related">
      <span className="rel-lab">{label}</span>
      <ul className="rel-list" aria-label={label}>
        {items.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              className={cx('pill', pill, 'rel-btn')}
              onClick={() => onGoTo({ kind: item.kind, key: item.key })}
              title={item.detail ? `${item.label} · ${item.detail}` : item.label}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

interface RowPinProps {
  pinned: boolean
  onTogglePin: (pinned: boolean) => void
  onOpenSearch: (id: string) => void
}

function CompanyRow({
  company,
  pinned,
  onTogglePin,
  onOpenSearch,
  jobs,
  people,
  onGoTo,
}: {
  company: CompanyEntity
  jobs: RelatedEntity[]
  people: RelatedEntity[]
  onGoTo: (target: Focus) => void
} & RowPinProps) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="rtop">
        <span className="co-ico">
          <Icon name="building" size="lg" />
        </span>
        <div className="rmain">
          <Title href={company.url} label="opens company page">
            {company.name}
          </Title>
          {company.description && <p className="rdesc">{company.description}</p>}
          <div className="rmeta">
            <span className="pill job">
              {company.job_count} {company.job_count === 1 ? 'job' : 'jobs'}
            </span>
            <span className="pill per">
              {company.person_count} {company.person_count === 1 ? 'person' : 'people'}
            </span>
          </div>
        </div>
        <PinToggle name={company.name} isPinned={pinned} onChange={onTogglePin} />
      </div>
      {company.alignment && (
        <>
          <div className="ract">
            <Disclosure label="How you align" open={open} onToggle={() => setOpen(!open)} />
          </div>
          <Note label="How you align" text={company.alignment} open={open} />
        </>
      )}
      <Related label="Jobs" items={jobs} onGoTo={onGoTo} />
      <Related label="People to connect with" items={people} onGoTo={onGoTo} />
      <SeenIn sighting={company} onOpenSearch={onOpenSearch} />
    </>
  )
}

function JobRow({
  job,
  applied,
  onToggle,
  pinned,
  onTogglePin,
  onOpenSearch,
  people,
  onGoTo,
}: {
  job: JobEntity
  applied: boolean
  onToggle: (active: boolean) => void
  people: RelatedEntity[]
  onGoTo: (target: Focus) => void
} & RowPinProps) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="rtop">
        <div className="rmain">
          <Title href={job.url} label="opens job posting">
            {job.title}
          </Title>
          <div className="rmeta">
            <CompanyTag name={job.company} />
            {job.location && (
              <span>
                <Icon name="pin2" size="sm" />
                {job.location}
              </span>
            )}
            {job.salary && <span className="sal">{job.salary}</span>}
          </div>
        </div>
        <PinToggle name={job.title} isPinned={pinned} onChange={onTogglePin} />
      </div>
      <div className="ract">
        <StatusToggle kind="job" name={job.title} isSelected={applied} onChange={onToggle} />
        {job.alignment && (
          <Disclosure label="How you align" open={open} onToggle={() => setOpen(!open)} />
        )}
      </div>
      {job.alignment && <Note label="How you align" text={job.alignment} open={open} />}
      <Related label="People to connect with" items={people} onGoTo={onGoTo} />
      <SeenIn sighting={job} onOpenSearch={onOpenSearch} />
    </>
  )
}

function PersonRow({
  person,
  connected,
  onToggle,
  pinned,
  onTogglePin,
  onOpenSearch,
  jobs,
  onGoTo,
}: {
  person: PersonEntity
  connected: boolean
  onToggle: (active: boolean) => void
  jobs: RelatedEntity[]
  onGoTo: (target: Focus) => void
} & RowPinProps) {
  const toast = useToast()
  const [why, setWhy] = useState(false)
  const [message, setMessage] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(person.connect_message ?? '')
      toast('Message copied to clipboard')
    } catch {
      toast('Could not copy. Select the text and copy it instead.')
    }
  }
  return (
    <>
      <div className="rtop">
        <span className="pavatar" aria-hidden="true">
          {initials(person.name)}
        </span>
        <div className="rmain">
          <Title href={person.profile_url} label="opens LinkedIn profile">
            {person.name}
          </Title>
          <div className="rmeta">
            {person.title && <span>{person.title}</span>}
            {person.shared_background && (
              <span className="pill per tight">{person.shared_background}</span>
            )}
            <CompanyTag name={person.company} />
          </div>
        </div>
        <PinToggle name={person.name} isPinned={pinned} onChange={onTogglePin} />
      </div>
      <div className="ract">
        <StatusToggle kind="person" name={person.name} isSelected={connected} onChange={onToggle} />
        {person.alignment && (
          <Disclosure label="Why connect" open={why} onToggle={() => setWhy(!why)} />
        )}
        {person.connect_message && (
          <Disclosure
            label="Example LinkedIn message"
            open={message}
            onToggle={() => setMessage(!message)}
          />
        )}
      </div>
      {person.alignment && <Note label="Why connect" text={person.alignment} variant="p" open={why} />}
      {person.connect_message && (
        <Note
          label={`Example LinkedIn message · ${person.connect_message.length} characters`}
          text={person.connect_message}
          variant="p"
          open={message}
        >
          <div className="acts">
            <button type="button" className="btn xs" onClick={copy}>
              <Icon name="copy" size="sm" />
              Copy
            </button>
          </div>
        </Note>
      )}
      <Related label="Jobs at this company" items={jobs} onGoTo={onGoTo} />
      <SeenIn sighting={person} onOpenSearch={onOpenSearch} />
    </>
  )
}
