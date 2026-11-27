import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  CompanyResult,
  JobResult,
  PersonResult,
  PinKind,
  PinMap,
  SearchResults,
  StatusKind,
  StatusMap,
} from '@/api'
import { ConnectDrawer, type DrawerPerson } from '@/components/connect-drawer'
import { FindPeopleButton, FindPeopleSearch } from '@/components/find-people-button'
import { PageHeader } from '@/components/page-header'
import { Icon } from '@/components/icon'
import { PinToggle } from '@/components/pin-toggle'
import { StatusToggle } from '@/components/status-toggle'
import { useToast } from '@/utils/use-toast'
import { cx } from '@/utils/cx'
import { uiZoom } from '@/utils/ui-zoom'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'
import { initials } from '@/utils/initials'

type ToggleStatus = (kind: StatusKind, key: string, active: boolean) => void
type TogglePin = (kind: PinKind, key: string, pinned: boolean) => void
/** A company came back from an on-demand people search; replace it in the results. */
type CompanyFound = (company: CompanyResult) => void

/** Rows shown per pane before "Show N more". */
const PANE_LIMIT = 3
/** "Strong fit" filter threshold. */
const STRONG_FIT = 75

export interface SearchMeta {
  title: string
  location: string
  /** When the search ran (ISO). */
  createdAt: string | null
  /** Labels of the boards it searched. */
  boards: string[]
}

interface ResultsProps {
  results: SearchResults
  meta: SearchMeta
  /** APPLIED / CONNECTED marks for the current user, by entity key. */
  entityStatuses: StatusMap
  statusError: string | null
  onToggleStatus: ToggleStatus
  /** Pinned companies / jobs / people for the current user, by entity key. */
  pins: PinMap
  pinError: string | null
  onTogglePin: TogglePin
  /** Id of the saved search shown; on-demand people searches need it. Null until saved. */
  searchId: string | null
  onCompanyFound: CompanyFound
  /** Back to the form with this search's parameters. */
  onEdit: () => void
  onNewSearch: () => void
}

type Filter = 'hasJob' | 'hasPeople' | 'strong' | 'notApplied' | 'pinned'
type SortId = 'fit' | 'pinned' | 'name' | 'jobs' | 'people'

const FILTERS: { id: Filter; label: string; icon?: 'briefcase' | 'users' | 'pin' }[] = [
  { id: 'hasJob', label: 'Has open job', icon: 'briefcase' },
  { id: 'hasPeople', label: 'Has contact', icon: 'users' },
  { id: 'strong', label: `Strong fit ${STRONG_FIT}+` },
  { id: 'notApplied', label: 'Not applied' },
  { id: 'pinned', label: 'Pinned', icon: 'pin' },
]

const SORTS: { id: SortId; label: string }[] = [
  { id: 'fit', label: 'Best fit first' },
  { id: 'pinned', label: 'Pinned first' },
  { id: 'name', label: 'Name A-Z' },
  { id: 'jobs', label: 'Most jobs' },
  { id: 'people', label: 'Most contacts' },
]

/** A company with its rank in the agent's order and a stable id for the DOM. */
interface Ranked {
  company: CompanyResult
  rank: number
  id: string
}

const fitClass = (score: number) => (score >= 80 ? 'strong' : score >= 70 ? 'good' : 'fair')
const fitLabel = (score: number) =>
  score >= 80 ? 'Strong fit' : score >= 70 ? 'Good fit' : 'Possible fit'
const scoreClass = (score: number) => (score >= 80 ? 's1' : score >= 70 ? 's2' : '')
const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name
const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

function bestJob(company: CompanyResult): JobResult | undefined {
  return company.jobs.toSorted((a, b) => (b.score ?? -1) - (a.score ?? -1))[0]
}

/** Everything a row needs from the page: marks, pins and the actions on them. */
interface RowContext {
  statuses: StatusMap
  pins: PinMap
  pin: (kind: PinKind, key: string, name: string, pinned: boolean) => void
  onToggleStatus: ToggleStatus
  message: (person: PersonResult, company: CompanyResult) => void
  goCompany: (id: string) => void
  searchId: string | null
  onCompanyFound: CompanyFound
}

export function Results({
  results,
  meta,
  entityStatuses,
  statusError,
  onToggleStatus,
  pins,
  pinError,
  onTogglePin,
  searchId,
  onCompanyFound,
  onEdit,
  onNewSearch,
}: ResultsProps) {
  const toast = useToast()
  const ranked: Ranked[] = useMemo(
    () =>
      results.companies.map((company, index) => ({
        company,
        rank: index + 1,
        id: `co-${index + 1}`,
      })),
    [results.companies],
  )

  const [group, setGroup] = useState<'company' | 'type'>('company')
  const [open, setOpen] = useState<Set<string>>(() => new Set())
  const [filters, setFilters] = useState<Set<Filter>>(new Set())
  const [sort, setSort] = useState<SortId>('fit')
  const [active, setActive] = useState<string | null>(ranked[0]?.id ?? null)
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [drawer, setDrawer] = useState<{ person: PersonResult; company: CompanyResult } | null>(
    null,
  )
  /** A panel to scroll to once it has rendered (open) in the company view. */
  const scrollTarget = useRef<string | null>(null)

  const isPinned = (kind: PinKind, key: string | undefined) => !!key && !!pins[kind][key]
  const anyPinned = (company: CompanyResult) =>
    isPinned('company', company.key) ||
    company.jobs.some((job) => isPinned('job', job.key)) ||
    company.people.some((person) => isPinned('person', person.key))
  const visibleJobs = (company: CompanyResult) =>
    filters.has('notApplied')
      ? company.jobs.filter((job) => !entityStatuses.job[job.key])
      : company.jobs

  const shown = ranked
    .filter(({ company }) => {
      if (filters.has('hasJob') && company.jobs.length === 0) return false
      if (filters.has('hasPeople') && company.people.length === 0) return false
      if (filters.has('strong') && (company.score ?? 0) < STRONG_FIT) return false
      if (filters.has('pinned') && !anyPinned(company)) return false
      if (filters.has('notApplied') && visibleJobs(company).length === 0) return false
      return true
    })
    .toSorted((a, b) => {
      const byRank = a.rank - b.rank
      switch (sort) {
        case 'pinned':
          return Number(anyPinned(b.company)) - Number(anyPinned(a.company)) || byRank
        case 'name':
          return a.company.name.localeCompare(b.company.name)
        case 'jobs':
          return b.company.jobs.length - a.company.jobs.length || byRank
        case 'people':
          return b.company.people.length - a.company.people.length || byRank
        default:
          return byRank
      }
    })

  // Scroll spy: highlight the company whose panel is at the top of the screen.
  useEffect(() => {
    if (group !== 'company') return
    const onScroll = () => {
      let current: string | null = null
      document.querySelectorAll<HTMLElement>('.co-panel[id]').forEach((panel) => {
        if (panel.getBoundingClientRect().top < 220 * uiZoom()) current = panel.id
      })
      if (current) setActive(current)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [group])

  useEffect(() => {
    const id = scrollTarget.current
    if (!id) return
    scrollTarget.current = null
    document.getElementById(id)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  })

  const goCompany = (id: string) => {
    setGroup('company')
    setOpen((current) => new Set(current).add(id))
    setActive(id)
    scrollTarget.current = id
  }

  const toggleOpen = (id: string) => {
    setOpen((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })
    setActive(id)
  }

  const pin = (kind: PinKind, key: string, name: string, pinned: boolean) => {
    onTogglePin(kind, key, pinned)
    toast(`${pinned ? 'Pinned' : 'Unpinned'} ${name}`, () => onTogglePin(kind, key, !pinned))
  }

  const ctx: RowContext = {
    statuses: entityStatuses,
    pins,
    pin,
    onToggleStatus,
    message: (person, company) => setDrawer({ person, company }),
    goCompany,
    searchId,
    onCompanyFound,
  }

  // Totals across the whole search, for the summary strip.
  const allJobs = results.companies.flatMap((company) => company.jobs)
  const allPeople = results.companies.flatMap((company) => company.people)
  const applied = allJobs.filter((job) => entityStatuses.job[job.key]).length
  const connected = allPeople.filter((person) => entityStatuses.person[person.key]).length
  const pinnedCount =
    results.companies.filter((company) => isPinned('company', company.key)).length +
    allJobs.filter((job) => isPinned('job', job.key)).length +
    allPeople.filter((person) => isPinned('person', person.key)).length

  const shownJobs = shown.reduce((sum, { company }) => sum + visibleJobs(company).length, 0)
  const shownPeople = shown.reduce((sum, { company }) => sum + company.people.length, 0)

  const created = meta.createdAt ? new Date(meta.createdAt) : null
  const drawerPerson = useMemo<DrawerPerson | null>(
    () =>
      drawer && {
        name: drawer.person.name,
        title: drawer.person.title,
        company: drawer.company.name,
        profileUrl: drawer.person.profile_url,
        alignment: drawer.person.alignment,
        message: drawer.person.connect_message,
        key: drawer.person.key,
      },
    [drawer],
  )

  return (
    <div className="wrap">
      <PageHeader
        crumbs={
          <>
            <button type="button" className="crumb-link" onClick={onEdit}>
              Search
            </button>
            <span aria-hidden="true">/</span>
            <span>Results</span>
          </>
        }
        title={meta.title || 'Your opportunities'}
        subtitle={
          <>
            {meta.location && (
              <span>
                <Icon name="pin2" size="sm" />
                {meta.location}
              </span>
            )}
            {created && (
              <span>
                <Icon name="clock" size="sm" />
                Searched{' '}
                <time dateTime={meta.createdAt ?? undefined} title={fullDateFormat.format(created)}>
                  {formatRelativeDate(created)}
                </time>
              </span>
            )}
            {meta.boards.length > 0 && (
              <span>
                <Icon name="layers" size="sm" />
                {meta.boards.join(', ')}
              </span>
            )}
          </>
        }
        actions={
          <>
            <button type="button" className="btn sm" onClick={onEdit}>
              Edit and re-run
            </button>
            <button type="button" className="btn pri sm" onClick={onNewSearch}>
              <Icon name="plus" /> New search
            </button>
          </>
        }
      />

      {statusError && <ErrorBanner message={statusError} />}
      {pinError && <ErrorBanner message={pinError} />}

      <section className="strip" aria-label="Summary">
        <div className="stats" role="list" aria-label="Search totals">
          <Stat kind="co" value={results.companies.length} label="Companies" />
          <Stat kind="job" value={allJobs.length} label="Jobs" sub={`${applied} applied`} />
          <Stat
            kind="per"
            value={allPeople.length}
            label="People"
            sub={`${connected} connected`}
          />
          <Stat kind="pin" value={pinnedCount} label="Pinned" />
        </div>
        {results.summary && (
          <div className="sumline">
            <Icon name="sparkle" size="sm" />
            <p className={cx(!summaryOpen && 'clamp')}>{results.summary}</p>
            <button
              type="button"
              className="more"
              aria-expanded={summaryOpen}
              onClick={() => setSummaryOpen((current) => !current)}
            >
              {summaryOpen ? 'Show less' : 'Read full summary'}
            </button>
          </div>
        )}
      </section>

      <div className="cols">
        <div className="rail">
          <div className="toolbar" role="toolbar" aria-label="View options">
            <span className="tb-lab" id="group-by">
              Group by
            </span>
            <div className="seg" role="group" aria-labelledby="group-by">
              {(['company', 'type'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={group === option}
                  onClick={() => {
                    setGroup(option)
                    window.scrollTo?.({ top: 0 })
                  }}
                >
                  <Icon name={option === 'company' ? 'building' : 'list'} size="sm" />
                  {option === 'company' ? 'Company' : 'Type'}
                </button>
              ))}
            </div>
            <div className="chips" role="group" aria-label="Filters">
              {FILTERS.map((filter) => (
                <button
                  key={filter.id}
                  type="button"
                  className="chip"
                  aria-pressed={filters.has(filter.id)}
                  onClick={() =>
                    setFilters((current) => {
                      const next = new Set(current)
                      if (!next.delete(filter.id)) next.add(filter.id)
                      return next
                    })
                  }
                >
                  {filter.icon && <Icon name={filter.icon} />}
                  {filter.label}
                </button>
              ))}
            </div>
            <span className="sp" />
            <label className="tb-lab" htmlFor="results-sort">
              Sort
            </label>
            <select
              id="results-sort"
              value={sort}
              onChange={(event) => setSort(event.target.value as SortId)}
            >
              {SORTS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        <nav className="index" aria-label={group === 'company' ? 'Jump to company' : 'Jump to'}>
          {group === 'company' ? (
            <>
              <h2>Jump to company</h2>
              <ol>
                {shown.map(({ company, rank, id }) => (
                  <li key={id}>
                    <button
                      type="button"
                      aria-current={active === id ? 'true' : undefined}
                      onClick={() => goCompany(id)}
                    >
                      <span className="rk num">{rank}</span>
                      <span className="nm">{company.name}</span>
                      {anyPinned(company) && (
                        <span className="pn" title="Has pinned items">
                          <Icon name="pin" />
                        </span>
                      )}
                      {company.score != null && <span className="sc num">{company.score}</span>}
                    </button>
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <>
              <h2>Jump to</h2>
              <ol>
                {(
                  [
                    ['companies', 'building', 'Companies'],
                    ['jobs', 'briefcase', 'Jobs'],
                    ['people', 'users', 'People'],
                  ] as const
                ).map(([id, icon, label]) => (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() =>
                        document
                          .getElementById(`t-${id}`)
                          ?.scrollIntoView?.({ behavior: 'smooth' })
                      }
                    >
                      <span className="rk">
                        <Icon name={icon} size="sm" />
                      </span>
                      <span className="nm">{label}</span>
                    </button>
                  </li>
                ))}
              </ol>
            </>
          )}
        </nav>
        </div>

        <section aria-label="Results">
          <h2 className="sr">{group === 'company' ? 'Companies' : 'Results by type'}</h2>
          <div className="count-line">
            <span aria-live="polite">
              Showing {shown.length} of {plural(ranked.length, 'company', 'companies')} ·{' '}
              {plural(shownJobs, 'job', 'jobs')} · {plural(shownPeople, 'person', 'people')}
            </span>
            {group === 'company' && shown.length > 0 && (
              <span className="chips">
                <button
                  type="button"
                  className="btn xs ghost"
                  onClick={() => setOpen(new Set(shown.map(({ id }) => id)))}
                >
                  <Icon name="expand" size="sm" />
                  Expand all
                </button>
                <button type="button" className="btn xs ghost" onClick={() => setOpen(new Set())}>
                  <Icon name="collapse" size="sm" />
                  Collapse all
                </button>
              </span>
            )}
          </div>

          {ranked.length === 0 ? (
            <div className="card empty big">
              <b>No matching companies found</b>
              <span>Try broadening what you are looking for.</span>
              <button type="button" className="btn pri sm" onClick={onEdit}>
                Edit and re-run
              </button>
            </div>
          ) : shown.length === 0 ? (
            <div className="card empty big">
              <b>No companies match these filters</b>
              <span>Try removing a filter to see the rest of your results.</span>
              <button type="button" className="btn pri sm" onClick={() => setFilters(new Set())}>
                Clear filters
              </button>
            </div>
          ) : group === 'company' ? (
            <div className="list">
              {shown.map((entry) => (
                <CompanyPanel
                  key={entry.id}
                  entry={entry}
                  open={open.has(entry.id)}
                  onToggle={() => toggleOpen(entry.id)}
                  jobs={visibleJobs(entry.company)}
                  notApplied={filters.has('notApplied')}
                  pinnedInside={anyPinned(entry.company)}
                  ctx={ctx}
                />
              ))}
            </div>
          ) : (
            <TypeView shown={shown} visibleJobs={visibleJobs} anyPinned={anyPinned} ctx={ctx} />
          )}
        </section>
      </div>

      <ConnectDrawer
        person={drawerPerson}
        connected={!!drawer && !!entityStatuses.person[drawer.person.key]}
        onToggleConnected={(value) => {
          if (!drawer) return
          onToggleStatus('person', drawer.person.key, value)
          toast(value ? 'Marked as connected' : 'Marked as not connected')
        }}
        onClose={() => setDrawer(null)}
      />
    </div>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="alert">
      <Icon name="alert" />
      <span>{message}</span>
    </div>
  )
}

function Stat({
  kind,
  value,
  label,
  sub,
}: {
  kind: 'co' | 'job' | 'per' | 'pin'
  value: number
  label: string
  sub?: string
}) {
  return (
    <div className={`stat ${kind}`} role="listitem">
      <span className="n num">{value}</span>
      <span className="l">{label}</span>
      {sub && <span className="s num">{sub}</span>}
    </div>
  )
}

function FitMeter({ score }: { score: number | null | undefined }) {
  if (score == null) return null
  return (
    <span className={`fit ${fitClass(score)}`}>
      <b className="num">{score}</b>
      <span className="bar">
        <i style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </span>
      <small>{fitLabel(score)}</small>
    </span>
  )
}

function Counts({ company }: { company: CompanyResult }) {
  return (
    <span className="counts">
      <span className="pill job">
        <Icon name="briefcase" size="sm" />
        {plural(company.jobs.length, 'job', 'jobs')}
      </span>
      {company.people.length > 0 ? (
        <span className="pill per">
          <Icon name="users" size="sm" />
          {plural(company.people.length, 'person', 'people')}
        </span>
      ) : (
        <span className="pill neu">No contacts yet</span>
      )}
    </span>
  )
}

function CompanyPanel({
  entry,
  open,
  onToggle,
  jobs,
  notApplied,
  pinnedInside,
  ctx,
}: {
  entry: Ranked
  open: boolean
  onToggle: () => void
  /** The jobs the filters leave visible. */
  jobs: JobResult[]
  notApplied: boolean
  pinnedInside: boolean
  ctx: RowContext
}) {
  const { company, rank, id } = entry
  const [alignOpen, setAlignOpen] = useState(false)
  const [allJobs, setAllJobs] = useState(false)
  const [allPeople, setAllPeople] = useState(false)
  const best = bestJob(company)
  const companyPinned = !!company.key && !!ctx.pins.company[company.key]
  const appliedHere = company.jobs.filter((job) => ctx.statuses.job[job.key]).length
  const bodyId = `${id}-body`
  const jobsShown = allJobs ? jobs : jobs.slice(0, PANE_LIMIT)
  const peopleShown = allPeople ? company.people : company.people.slice(0, PANE_LIMIT)
  const hiddenJobs = jobs.length - jobsShown.length
  const hiddenPeople = company.people.length - peopleShown.length

  return (
    <article className={cx('co-panel', pinnedInside && 'pinned')} id={id} data-open={open}>
      <div className="chead">
        <h3>
          <button
            type="button"
            className="ctoggle"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={onToggle}
          >
            <span className="co-ico">
              <Icon name="building" size="lg" />
            </span>
            <span>
              <span className="cname">
                <span className="cn">{company.name}</span>
                <span className="rank num">#{rank}</span>
                {pinnedInside && !companyPinned && (
                  <span className="pill pin">
                    <Icon name="pin" size="sm" />
                    Pinned item
                  </span>
                )}
              </span>
              {company.description && <span className="cdesc">{company.description}</span>}
              {best && (
                <span className="cbest">
                  <Icon name="briefcase" size="sm" />
                  <span className="bt">
                    Best match: <b>{best.title}</b>
                  </span>
                  {best.score != null && (
                    <span className={cx('score num', scoreClass(best.score))}>{best.score}</span>
                  )}
                </span>
              )}
            </span>
            <span className="cmeta">
              <Counts company={company} />
              <FitMeter score={company.score} />
            </span>
            <Icon name="chevron" className="chev" />
          </button>
        </h3>
        {company.key && (
          <PinToggle
            name={company.name}
            isPinned={companyPinned}
            onChange={(pinned) => ctx.pin('company', company.key!, company.name, pinned)}
          />
        )}
      </div>
      {open && (
        <div className="cbody" id={bodyId}>
          {company.alignment && (
            <div className="aligned">
              <Icon name="sparkle" />
              <div>
                <div className="lab">How you align</div>
                <p className={cx(!alignOpen && 'clamp')}>{company.alignment}</p>
                <button
                  type="button"
                  className="more"
                  aria-expanded={alignOpen}
                  onClick={() => setAlignOpen((current) => !current)}
                >
                  {alignOpen ? 'Show less' : 'Read more'}
                </button>
              </div>
            </div>
          )}
          {company.url && (
            <div className="cdetail">
              <a href={company.url} target="_blank" rel="noreferrer">
                {company.name} company page
                <span className="sr"> (opens in a new tab)</span>
              </a>
            </div>
          )}
          <div className="two">
            <section className="pane jobs" aria-label={`Jobs at ${company.name}`}>
              <header>
                <h4>
                  <Icon name="briefcase" />
                  Open jobs <span className="c num">{jobs.length}</span>
                </h4>
                {appliedHere > 0 && <span className="pill app num">{appliedHere} applied</span>}
              </header>
              {jobs.length > 0 ? (
                <ul className="rows">
                  {jobsShown.map((job, index) => (
                    <JobRow key={`${job.key || job.url}-${index}`} job={job} company={company} ctx={ctx} />
                  ))}
                </ul>
              ) : (
                <div className="empty">
                  {notApplied ? 'No matching jobs left to apply to.' : 'No matching jobs found.'}
                </div>
              )}
              {hiddenJobs > 0 && (
                <footer>
                  <button type="button" className="btn xs" onClick={() => setAllJobs(true)}>
                    Show {plural(hiddenJobs, 'more job', 'more jobs')}
                    <Icon name="chevron" size="sm" />
                  </button>
                </footer>
              )}
            </section>
            <section className="pane people" aria-label={`People at ${company.name}`}>
              <header>
                <h4>
                  <Icon name="users" />
                  People to connect with <span className="c num">{company.people.length}</span>
                </h4>
              </header>
              {company.people.length > 0 ? (
                <ul className="rows">
                  {peopleShown.map((person, index) => (
                    <PersonRow
                      key={`${person.key || person.profile_url}-${index}`}
                      person={person}
                      company={company}
                      ctx={ctx}
                    />
                  ))}
                </ul>
              ) : (
                <div className="empty">
                  <span>
                    {company.people_searched
                      ? 'No current employees found yet.'
                      : 'You have not searched for contacts here yet.'}
                  </span>
                </div>
              )}
              {(hiddenPeople > 0 || company.key) && (
                <footer>
                  {hiddenPeople > 0 && (
                    <button type="button" className="btn xs" onClick={() => setAllPeople(true)}>
                      Show {plural(hiddenPeople, 'more person', 'more people')}
                      <Icon name="chevron" size="sm" />
                    </button>
                  )}
                  {company.key && (
                    <FindPeopleSearch
                      searchId={ctx.searchId}
                      companyKey={company.key}
                      target={company.name}
                      label="Find more people"
                      onFound={ctx.onCompanyFound}
                    />
                  )}
                </footer>
              )}
            </section>
          </div>
        </div>
      )}
    </article>
  )
}

/** The row's own toggled note ("How you align" / "Why connect"). */
function useNote() {
  const [open, setOpen] = useState(false)
  return { open, toggle: () => setOpen((current) => !current) }
}

function ExtTitle({ href, children, label }: { href: string; children: string; label: string }) {
  if (!href) return <span className="rtitle plain">{children}</span>
  return (
    <a className="rtitle" href={href} target="_blank" rel="noreferrer">
      {children}
      <Icon name="ext" />
      <span className="sr"> ({label})</span>
    </a>
  )
}

function CompanyTag({ company, ctx, id }: { company: CompanyResult; ctx: RowContext; id?: string }) {
  if (!id) return null
  return (
    <button type="button" className="cotag" onClick={() => ctx.goCompany(id)}>
      <Icon name="building" />
      {company.name}
    </button>
  )
}

function JobRow({
  job,
  company,
  ctx,
  companyId,
}: {
  job: JobResult
  company: CompanyResult
  ctx: RowContext
  /** Type view: show a tag that jumps to the company. */
  companyId?: string
}) {
  const note = useNote()
  const pinned = !!job.key && !!ctx.pins.job[job.key]
  const applied = !!job.key && !!ctx.statuses.job[job.key]
  const people = company.people
  const canFind = !!company.key && !!job.key
  const findForJob = (variant: 'link' | 'button') =>
    canFind && (
      <FindPeopleButton
        searchId={ctx.searchId}
        companyKey={company.key!}
        jobKey={job.key}
        target={`${job.title} at ${company.name}`}
        label="Find people for this role"
        variant={variant}
        onFound={ctx.onCompanyFound}
      />
    )
  return (
    <li className={cx('row', pinned && 'pinned', applied && 'done')}>
      <div className="rtop">
        <div className="rmain">
          <ExtTitle href={job.url} label="opens job posting">
            {job.title}
          </ExtTitle>
          <div className="rmeta">
            <CompanyTag company={company} ctx={ctx} id={companyId} />
            {job.location && (
              <span>
                <Icon name="pin2" size="sm" />
                {job.location}
              </span>
            )}
            {job.salary && <span className="sal">{job.salary}</span>}
            {job.score != null && (
              <span className={cx('score num', scoreClass(job.score))} title="Match score">
                {job.score} match
              </span>
            )}
          </div>
        </div>
        {job.key && (
          <PinToggle
            name={job.title}
            isPinned={pinned}
            onChange={(value) => ctx.pin('job', job.key, job.title, value)}
          />
        )}
      </div>
      {(job.key || job.alignment) && (
        <div className="ract">
          {job.key && (
            <StatusToggle
              kind="job"
              name={job.title}
              isSelected={applied}
              onChange={(value) => ctx.onToggleStatus('job', job.key, value)}
            />
          )}
          {job.alignment && (
            <button type="button" className="disc" aria-expanded={note.open} onClick={note.toggle}>
              How you align <Icon name="chevron" />
            </button>
          )}
        </div>
      )}
      {job.alignment && (
        <div className="note" hidden={!note.open}>
          <div className="lab">How you align</div>
          {job.alignment}
          {people.length > 0 && canFind && <div className="acts">{findForJob('link')}</div>}
        </div>
      )}
      {people.length > 0 ? (
        <div className="crosslink">
          <span className="avs" aria-hidden="true">
            {people.slice(0, 3).map((person, index) => (
              <span className="pavatar" key={index}>
                {initials(person.name)}
              </span>
            ))}
          </span>
          <button type="button" className="xlink per" onClick={() => ctx.message(people[0], company)}>
            Message {firstName(people[0].name)}
            {people.length > 1 &&
              ` or ${people.length - 1} other${people.length > 2 ? 's' : ''}`}{' '}
            about this role <Icon name="arrow" />
          </button>
        </div>
      ) : (
        canFind && <div className="crosslink">{findForJob('link')}</div>
      )}
    </li>
  )
}

function PersonRow({
  person,
  company,
  ctx,
  companyId,
}: {
  person: PersonResult
  company: CompanyResult
  ctx: RowContext
  companyId?: string
}) {
  const note = useNote()
  const pinned = !!person.key && !!ctx.pins.person[person.key]
  const connected = !!person.key && !!ctx.statuses.person[person.key]
  return (
    <li className={cx('row', pinned && 'pinned', connected && 'done')}>
      <div className="rtop">
        <span className="pavatar" aria-hidden="true">
          {initials(person.name)}
        </span>
        <div className="rmain">
          <ExtTitle href={person.profile_url} label="opens LinkedIn profile">
            {person.name}
          </ExtTitle>
          <div className="rmeta">
            <CompanyTag company={company} ctx={ctx} id={companyId} />
            {person.title && <span>{person.title}</span>}
            {person.shared_background && (
              <span className="pill per tight">{person.shared_background}</span>
            )}
          </div>
        </div>
        {person.key && (
          <PinToggle
            name={person.name}
            isPinned={pinned}
            onChange={(value) => ctx.pin('person', person.key, person.name, value)}
          />
        )}
      </div>
      {(person.key || person.alignment) && (
        <div className="ract">
          {person.key && (
            <StatusToggle
              kind="person"
              name={person.name}
              isSelected={connected}
              onChange={(value) => ctx.onToggleStatus('person', person.key, value)}
            />
          )}
          {person.alignment && (
            <button type="button" className="disc" aria-expanded={note.open} onClick={note.toggle}>
              Why connect <Icon name="chevron" />
            </button>
          )}
        </div>
      )}
      {person.alignment && (
        <div className="note p" hidden={!note.open}>
          <div className="lab">Why connect</div>
          {person.alignment}
        </div>
      )}
      <div className="crosslink">
        <button type="button" className="xlink per" onClick={() => ctx.message(person, company)}>
          <Icon name="send" />
          Message {firstName(person.name)} <Icon name="arrow" />
        </button>
      </div>
    </li>
  )
}

function TypeView({
  shown,
  visibleJobs,
  anyPinned,
  ctx,
}: {
  shown: Ranked[]
  visibleJobs: (company: CompanyResult) => JobResult[]
  anyPinned: (company: CompanyResult) => boolean
  ctx: RowContext
}) {
  const jobs = shown
    .flatMap((entry) => visibleJobs(entry.company).map((job) => ({ job, entry })))
    .toSorted((a, b) => (b.job.score ?? -1) - (a.job.score ?? -1))
  const people = shown.flatMap((entry) =>
    entry.company.people.map((person) => ({ person, entry })),
  )
  return (
    <>
      <section className="tsec" id="t-companies">
        <h2 className="co-d">
          <Icon name="building" size="lg" />
          Companies <span className="c pill co num">{shown.length}</span>
        </h2>
        <div className="list">
          {shown.map((entry) => (
            <div key={entry.id} className={cx('co-panel', anyPinned(entry.company) && 'pinned')}>
              <div className="chead">
                <button
                  type="button"
                  className="ctoggle"
                  aria-label={`Open ${entry.company.name} in company view`}
                  onClick={() => ctx.goCompany(entry.id)}
                >
                  <span className="co-ico">
                    <Icon name="building" size="lg" />
                  </span>
                  <span>
                    <span className="cname">
                      <span className="cn">{entry.company.name}</span>
                      <span className="rank num">#{entry.rank}</span>
                    </span>
                    {entry.company.description && (
                      <span className="cdesc">{entry.company.description}</span>
                    )}
                  </span>
                  <span className="cmeta">
                    <Counts company={entry.company} />
                    <FitMeter score={entry.company.score} />
                  </span>
                  <Icon name="arrow" className="chev" />
                </button>
                {entry.company.key && (
                  <PinToggle
                    name={entry.company.name}
                    isPinned={!!ctx.pins.company[entry.company.key]}
                    onChange={(value) =>
                      ctx.pin('company', entry.company.key!, entry.company.name, value)
                    }
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="tsec" id="t-jobs">
        <h2 className="job-d">
          <Icon name="briefcase" size="lg" />
          Jobs <span className="c pill job num">{jobs.length}</span>
        </h2>
        <div className="tcard">
          <ul className="rows">
            {jobs.map(({ job, entry }, index) => (
              <JobRow
                key={`${job.key || job.url}-${index}`}
                job={job}
                company={entry.company}
                companyId={entry.id}
                ctx={ctx}
              />
            ))}
          </ul>
        </div>
      </section>
      <section className="tsec" id="t-people">
        <h2 className="per-d">
          <Icon name="users" size="lg" />
          People <span className="c pill per num">{people.length}</span>
        </h2>
        <div className="tcard">
          <ul className="rows">
            {people.map(({ person, entry }, index) => (
              <PersonRow
                key={`${person.key || person.profile_url}-${index}`}
                person={person}
                company={entry.company}
                companyId={entry.id}
                ctx={ctx}
              />
            ))}
          </ul>
        </div>
      </section>
    </>
  )
}
