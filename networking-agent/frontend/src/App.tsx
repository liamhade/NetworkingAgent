import { useEffect, useRef, useState } from 'react'
import {
  getCurrentUser,
  getPins,
  getSearch,
  getStatuses,
  listSearches,
  setPin,
  setStatus,
  streamSearch,
  type CompanyResult,
  type PinKind,
  type PinMap,
  type SearchRequest,
  type SearchResults,
  type SearchSummary,
  type StatusKind,
  type StatusMap,
  type User,
} from '@/api'
import { SearchHistory } from '@/components/search-history'
import { TopNav } from '@/components/top-nav'
import { CompaniesPage, JobsPage, PeoplePage } from '@/pages/entities'
import { Hero } from '@/pages/hero'
import { Results } from '@/pages/results'
import { withRetry } from '@/utils/retry'
import { useKeyedToggles } from '@/utils/use-keyed-toggles'
import { type View, viewFromHash, viewHash } from '@/utils/view'

const EMPTY_FORM: SearchRequest = { background: '', location: '', looking_for: '' }
const EMPTY_STATUSES: StatusMap = { job: {}, person: {} }
const EMPTY_PINS: PinMap = { company: {}, job: {}, person: {} }

export default function App() {
  /** Top-level page, mirrored in the URL hash (`#/companies`, `#/jobs`, `#/people`). */
  const [view, setView] = useState<View>(() => viewFromHash(window.location.hash))
  /** Bumped whenever a search is saved, so the Companies/Jobs/People lists re-fetch. */
  const [entitiesVersion, setEntitiesVersion] = useState(0)
  const [page, setPage] = useState<'hero' | 'results'>('hero')
  const [form, setForm] = useState<SearchRequest>(EMPTY_FORM)
  const [statuses, setStatuses] = useState<string[]>([])
  const [results, setResults] = useState<SearchResults | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const abort = useRef<AbortController | null>(null)

  const [user, setUser] = useState<User | null>(null)
  const [history, setHistory] = useState<SearchSummary[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  /** The search on screen, for on-demand people searches that finish later. */
  const shownId = useRef<string | null>(null)
  useEffect(() => {
    shownId.current = activeId
  }, [activeId])

  /** APPLIED / CONNECTED marks and pins, by entity key; toggled optimistically. */
  const marks = useKeyedToggles<StatusKind>(
    EMPTY_STATUSES,
    setStatus,
    'Could not save that change. Please try again.',
  )
  const pinState = useKeyedToggles<PinKind>(
    EMPTY_PINS,
    setPin,
    'Could not save that pin. Please try again.',
  )
  const { map: entityStatuses, error: statusError, toggle: toggleStatus } = marks
  const { map: pins, error: pinError, toggle: togglePin } = pinState

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash(window.location.hash))
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navigate = (target: View) => {
    setView(target)
    if (viewFromHash(window.location.hash) !== target) window.location.hash = viewHash(target)
  }

  /**
   * Load the user's saved data. Each request retries with backoff, because the
   * backend is often still starting (or reloading) when the page first loads;
   * an error is only shown once every attempt has failed.
   */
  const loadUserData = (signal: AbortSignal) => {
    withRetry(getCurrentUser, signal)
      .then(setUser)
      .catch(() => {
        // The name is cosmetic; the panel works without it.
      })
    withRetry(listSearches, signal)
      .then((searches) => {
        setHistory(searches)
        setHistoryError(null)
      })
      .catch((caught: Error) => {
        if (!signal.aborted) setHistoryError('Could not load previous searches.')
        console.error(caught)
      })
      .finally(() => {
        if (!signal.aborted) setHistoryLoading(false)
      })
    withRetry(getStatuses, signal)
      .then(marks.load)
      .catch((caught: Error) => {
        if (!signal.aborted) marks.setError('Could not load APPLIED / CONNECTED marks.')
        console.error(caught)
      })
    withRetry(getPins, signal)
      .then(pinState.load)
      .catch((caught: Error) => {
        if (!signal.aborted) pinState.setError('Could not load your pins.')
        console.error(caught)
      })
  }

  useEffect(() => {
    const controller = new AbortController()
    loadUserData(controller.signal)
    return () => controller.abort()
  }, [])

  /** Cancel whatever the results page is currently doing and start a new task. */
  const restart = () => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setStatuses([])
    setResults(null)
    setError(null)
    setPage('results')
    navigate('search')
    window.scrollTo({ top: 0 })
    return controller
  }

  const search = async (request: SearchRequest) => {
    const controller = restart()
    setForm(request)
    setActiveId(null)
    setRunning(true)

    try {
      await streamSearch(
        request,
        (event) => {
          if (event.type === 'status') setStatuses((current) => [...current, event.message])
          else if (event.type === 'result') setResults(event.data)
          else if (event.type === 'saved') {
            setHistory((current) => [
              event.search,
              ...current.filter((entry) => entry.id !== event.search.id),
            ])
            setHistoryError(null)
            setEntitiesVersion((current) => current + 1)
            // The backend is clearly up now; recover the marks/pins if the first load failed.
            getStatuses().then(marks.load).catch(console.error)
            getPins().then(pinState.load).catch(console.error)
            if (!controller.signal.aborted) setActiveId(event.search.id)
          } else setError(event.message)
        },
        controller.signal,
      )
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message)
    } finally {
      if (abort.current === controller) setRunning(false)
    }
  }

  const openSaved = async (id: string) => {
    const controller = restart()
    setActiveId(id)
    setRunning(false)
    try {
      const saved = await getSearch(id, controller.signal)
      if (controller.signal.aborted) return
      setForm(saved.request)
      setResults(saved.results)
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message)
    }
  }

  const back = () => {
    abort.current?.abort()
    setRunning(false)
    setActiveId(null)
    setPage('hero')
    navigate('search')
  }

  const pinProps = { pins, pinError, onTogglePin: togglePin }

  /**
   * An on-demand people search finished: swap in the updated company, unless another search
   * is on screen by now. The People page re-fetches to show the new people.
   */
  const companyFound = (searchId: string, company: CompanyResult) => {
    setEntitiesVersion((current) => current + 1)
    if (shownId.current !== searchId) return
    setResults((current) =>
      current && {
        ...current,
        companies: current.companies.map((existing) =>
          existing.key === company.key ? company : existing,
        ),
      },
    )
  }

  return (
    <div className="flex min-h-svh bg-background-full">
      <SearchHistory
        searches={history}
        loading={historyLoading}
        error={historyError}
        activeId={activeId}
        user={user}
        onSelect={openSaved}
        onNewSearch={back}
      />
      <div className="min-w-0 flex-1">
        <TopNav view={view} />
        {view === 'companies' ? (
          <CompaniesPage
            refreshKey={entitiesVersion}
            onOpenSearch={openSaved}
            {...pinProps}
          />
        ) : view === 'jobs' ? (
          <JobsPage
            refreshKey={entitiesVersion}
            onOpenSearch={openSaved}
            entityStatuses={entityStatuses}
            statusError={statusError}
            onToggleStatus={toggleStatus}
            {...pinProps}
          />
        ) : view === 'people' ? (
          <PeoplePage
            refreshKey={entitiesVersion}
            onOpenSearch={openSaved}
            entityStatuses={entityStatuses}
            statusError={statusError}
            onToggleStatus={toggleStatus}
            {...pinProps}
          />
        ) : page === 'hero' ? (
          <Hero initial={form} onSubmit={search} />
        ) : (
          <Results
            statuses={statuses}
            results={results}
            error={error}
            running={running}
            entityStatuses={entityStatuses}
            statusError={statusError}
            onToggleStatus={toggleStatus}
            {...pinProps}
            searchId={activeId}
            onCompanyFound={(company) => activeId && companyFound(activeId, company)}
            onBack={back}
          />
        )}
      </div>
    </div>
  )
}
