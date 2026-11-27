import { useMemo, useState } from 'react'
import type {
  CompanyResult,
  PersonResult,
  PinKind,
  PinMap,
  SearchResults,
  StatusKind,
  StatusMap,
} from '@/api'
import { CompaniesWithoutJobs } from '@/components/results/companies-without-jobs'
import { JobCard } from '@/components/results/job-card'
import { ResultsRail } from '@/components/results/results-rail'
import type { RowContext } from '@/components/results/row-context'
import { StatsStrip } from '@/components/results/stats-strip'
import { ConnectDrawer, type DrawerPerson } from '@/components/connect-drawer'
import { PageHeader } from '@/components/page-header'
import { Icon } from '@/components/icon'
import { PanelResizer } from '@/components/panel-resizer'
import { useToast } from '@/utils/use-toast'
import { cx } from '@/utils/cx'
import { type PanelWidthSpec, usePanelWidth } from '@/utils/sidebar-width'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'
import {
  type Filter,
  type SortId,
  applyView,
  companyCounts,
  rankJobs,
  totals,
} from '@/utils/job-list'

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
  onToggleStatus: (kind: StatusKind, key: string, active: boolean) => void
  /** Pinned companies / jobs / people for the current user, by entity key. */
  pins: PinMap
  pinError: string | null
  onTogglePin: (kind: PinKind, key: string, pinned: boolean) => void
  /** Id of the saved search shown; on-demand people searches need it. Null until saved. */
  searchId: string | null
  /** A company came back from an on-demand people search; replace it in the results. */
  onCompanyFound: (company: CompanyResult) => void
  /** Back to the form with this search's parameters. */
  onEdit: () => void
  onNewSearch: () => void
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

const RAIL_OPEN_KEY = 'na-results-rail'
const RAIL_SPEC: PanelWidthSpec = { key: 'na-results-rail-width', initial: 220, min: 180, max: 420 }

/** Whether the results sidebar (filters + companies) is shown; remembered across visits. */
function useRailOpen(): [boolean, (open: boolean) => void] {
  const [open, setOpen] = useState(() => localStorage.getItem(RAIL_OPEN_KEY) !== 'closed')
  const update = (next: boolean) => {
    setOpen(next)
    localStorage.setItem(RAIL_OPEN_KEY, next ? 'open' : 'closed')
  }
  return [open, update]
}

const toggled = <T,>(set: ReadonlySet<T>, value: T): Set<T> => {
  const next = new Set(set)
  if (!next.delete(value)) next.add(value)
  return next
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
  const entries = useMemo(() => rankJobs(results.companies), [results.companies])
  const withoutJobs = useMemo(
    () => results.companies.filter((company) => company.jobs.length === 0),
    [results.companies],
  )
  const companies = useMemo(() => companyCounts(entries), [entries])
  const jobsPerCompany = useMemo(
    () => new Map(companies.map(({ id, jobs }) => [id, jobs])),
    [companies],
  )

  const [filters, setFilters] = useState<ReadonlySet<Filter>>(new Set())
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())
  const [sort, setSort] = useState<SortId>('fit')
  const [railOpen, setRailOpen] = useRailOpen()
  const railWidth = usePanelWidth(RAIL_SPEC)
  const [drawer, setDrawer] = useState<{ person: PersonResult; company: CompanyResult } | null>(
    null,
  )

  const marks = { statuses: entityStatuses, pins }
  const shown = applyView(entries, { filters, companies: selected, sort }, marks)

  const pin = (kind: PinKind, key: string, name: string, pinned: boolean) => {
    onTogglePin(kind, key, pinned)
    toast(`${pinned ? 'Pinned' : 'Unpinned'} ${name}`, () => onTogglePin(kind, key, !pinned))
  }
  const toggleCompany = (id: string) => setSelected((current) => toggled(current, id))

  const ctx: RowContext = {
    statuses: entityStatuses,
    pins,
    pin,
    onToggleStatus,
    message: (person, company) => setDrawer({ person, company }),
    toggleCompany,
    selectedCompanies: selected,
    searchId,
    onCompanyFound,
  }

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
  const clearFilters = () => {
    setFilters(new Set())
    setSelected(new Set())
  }

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
        subtitleOneLine
        subtitle={
          <>
            {created && (
              <span>
                <Icon name="clock" size="sm" />
                Searched{' '}
                <time dateTime={meta.createdAt ?? undefined} title={fullDateFormat.format(created)}>
                  {formatRelativeDate(created)}
                </time>
              </span>
            )}
            {meta.location && (
              <span>
                <Icon name="pin2" size="sm" />
                {meta.location}
              </span>
            )}
            {meta.boards.length > 0 && (
              <span className="meta-boards" title={meta.boards.join(', ')}>
                <Icon name="layers" size="sm" />
                <span>{meta.boards.join(', ')}</span>
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

      <StatsStrip totals={totals(results.companies, marks)} />

      <div
        className={cx('cols', !railOpen && 'rail-off')}
        style={{ '--rail-w': `${railWidth.width}px` } as React.CSSProperties}
      >
        {railOpen && (
          <div className="rail" id="results-rail">
            <ResultsRail
              filters={filters}
              onToggleFilter={(filter) => setFilters((current) => toggled(current, filter))}
              sort={sort}
              onSort={setSort}
              companies={companies}
              selected={selected}
              onToggleCompany={toggleCompany}
            />
          </div>
        )}
        {railOpen && (
          <PanelResizer
            {...railWidth}
            spec={RAIL_SPEC}
            label="Resize filters"
            controls="results-rail"
            className="rail-resize"
          />
        )}

        <section aria-label="Results">
          <h2 className="sr">Jobs</h2>
          <div className="count-line">
            <button
              type="button"
              className="ibtn rail-tog"
              aria-expanded={railOpen}
              aria-controls="results-rail"
              aria-label={railOpen ? 'Hide filters' : 'Show filters'}
              title={railOpen ? 'Hide filters' : 'Show filters'}
              onClick={() => setRailOpen(!railOpen)}
            >
              <Icon name="chevron" size="sm" className={railOpen ? 'left' : 'right'} />
            </button>
            <span aria-live="polite" className="count-text">
              Showing {shown.length} of {plural(entries.length, 'job', 'jobs')}
            </span>
          </div>

          {entries.length === 0 ? (
            withoutJobs.length === 0 && (
              <div className="card empty big">
                <b>No matching jobs found</b>
                <span>Try broadening what you are looking for.</span>
                <button type="button" className="btn pri sm" onClick={onEdit}>
                  Edit and re-run
                </button>
              </div>
            )
          ) : shown.length === 0 ? (
            <div className="card empty big">
              <b>No jobs match these filters</b>
              <span>Try removing a filter to see the rest of your results.</span>
              <button type="button" className="btn pri sm" onClick={clearFilters}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="list">
              {shown.map((entry) => (
                <JobCard
                  key={entry.id}
                  entry={entry}
                  otherJobs={(jobsPerCompany.get(entry.companyId) ?? 1) - 1}
                  ctx={ctx}
                />
              ))}
            </div>
          )}
          <CompaniesWithoutJobs companies={withoutJobs} />
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
