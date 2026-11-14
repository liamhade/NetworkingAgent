import { useEffect, useRef, useState } from 'react'
import {
  cancelSearch,
  deleteSearch,
  createSearchConfig,
  deleteSearchConfig,
  getCurrentUser,
  getPins,
  getSavedResume,
  getSearch,
  getSearchParams,
  getStatuses,
  listSearchConfigs,
  listSearches,
  setPin,
  setStatus,
  streamSearch,
  streamSearchEvents,
  updateSearchConfig,
  type AgentEvent,
  type CompanyResult,
  type PinKind,
  type PinMap,
  type SearchConfig,
  type SavedResume,
  type SearchRequest,
  type SearchResults,
  type SearchSummary,
  type StatusKind,
  type StatusMap,
  type User,
} from '@/api'
import { SearchConfigs } from '@/components/search-configs'
import { SearchHistory } from '@/components/search-history'
import { TopNav } from '@/components/top-nav'
import { CompaniesPage, JobsPage, PeoplePage } from '@/pages/entities'
import { Hero } from '@/pages/hero'
import { Results } from '@/pages/results'
import { withRetry } from '@/utils/retry'
import { useKeyedToggles } from '@/utils/use-keyed-toggles'
import { type View, viewFromHash, viewHash } from '@/utils/view'

const CANCELLED_MESSAGE = 'This search was cancelled.'

/** How often to re-list searches that are running where this page isn't watching them. */
const SEARCH_POLL_MS = 5000
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
  /** The resume saved on the server (null: none); shown on the search page as a file chip. */
  const [savedResume, setSavedResume] = useState<SavedResume | null>(null)
  /** Remounts the search form when the saved parameters arrive (it reads `initial` once). */
  const [formVersion, setFormVersion] = useState(0)
  /** Set once the user searches or reopens a past search, so a late restore can't clobber it. */
  const touched = useRef(false)
  /** The form as last reported by the search page, for "save current configuration". */
  const draft = useRef<SearchRequest>(EMPTY_FORM)
  const [configs, setConfigs] = useState<SearchConfig[]>([])
  const [configsLoading, setConfigsLoading] = useState(true)
  const [configsError, setConfigsError] = useState<string | null>(null)
  /** The configuration last loaded into (or saved from) the form. */
  const [activeConfigId, setActiveConfigId] = useState<string | null>(null)
  const [statuses, setStatuses] = useState<string[]>([])
  const [results, setResults] = useState<SearchResults | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const abort = useRef<AbortController | null>(null)

  const [user, setUser] = useState<User | null>(null)
  const [history, setHistory] = useState<SearchSummary[]>([])
  const historyRef = useRef<SearchSummary[]>([])
  useEffect(() => {
    historyRef.current = history
  }, [history])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
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
    withRetry(getSearchParams, signal)
      .then((params) => {
        if (!params || touched.current) return
        setForm(params)
        setFormVersion((current) => current + 1)
      })
      .catch((caught: Error) => console.error(caught)) // Defaults apply.
    withRetry(listSearchConfigs, signal)
      .then((loaded) => {
        setConfigs(loaded)
        setConfigsError(null)
      })
      .catch((caught: Error) => {
        if (!signal.aborted) setConfigsError('Could not load search configurations.')
        console.error(caught)
      })
      .finally(() => {
        if (!signal.aborted) setConfigsLoading(false)
      })
    withRetry(getSavedResume, signal)
      .then(setSavedResume)
      .catch((caught: Error) => console.error(caught))
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

  /** Add or update one search in the panel (new ones go on top). */
  const upsertHistory = (summary: SearchSummary) =>
    setHistory((current) =>
      current.some((entry) => entry.id === summary.id)
        ? current.map((entry) => (entry.id === summary.id ? summary : entry))
        : [summary, ...current],
    )

  /**
   * Show a search's event stream on the results page. The search itself runs on the server,
   * so aborting this stream (leaving, or opening another search) never stops it.
   */
  const follow = async (
    controller: AbortController,
    open: (onEvent: (event: AgentEvent) => void) => Promise<void>,
  ) => {
    let id: string | null = null
    try {
      await open((event) => {
        if (controller.signal.aborted) return
        if (event.type === 'started') {
          id = event.search.id
          upsertHistory(event.search)
          setHistoryError(null)
          setActiveId(id)
        } else if (event.type === 'status') setStatuses((current) => [...current, event.message])
        else if (event.type === 'result') setResults(event.data)
        else if (event.type === 'saved') {
          upsertHistory(event.search)
          setEntitiesVersion((current) => current + 1)
          // The backend is clearly up now; recover the marks/pins if the first load failed.
          getStatuses().then(marks.load).catch(console.error)
          getPins().then(pinState.load).catch(console.error)
        } else if (event.type === 'cancelled') {
          upsertHistory(event.search)
          setError(CANCELLED_MESSAGE)
        } else if (event.type === 'error') {
          setError(event.message)
          const failed = id
          if (failed) {
            setHistory((current) =>
              current.map((entry) =>
                entry.id === failed ? { ...entry, status: 'error' } : entry,
              ),
            )
          }
        }
      })
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message)
    } finally {
      if (abort.current === controller) setRunning(false)
    }
  }

  const search = async (request: SearchRequest) => {
    touched.current = true
    const controller = restart()
    setForm(request)
    setActiveId(null)
    setRunning(true)
    await follow(controller, (onEvent) => streamSearch(request, onEvent, controller.signal))
  }

  const openSaved = async (id: string) => {
    touched.current = true
    const controller = restart()
    setActiveId(id)
    setRunning(false)
    try {
      const saved = await getSearch(id, controller.signal)
      if (controller.signal.aborted) return
      setForm(saved.request)
      if (saved.status === 'running') {
        // Still searching: show its progress and follow it until it ends.
        setRunning(true)
        await follow(controller, (onEvent) => streamSearchEvents(id, onEvent, controller.signal))
      } else if (saved.status === 'cancelled') {
        setStatuses(saved.messages)
        setError(CANCELLED_MESSAGE)
      } else if (saved.status === 'error') {
        setStatuses(saved.messages)
        setError(saved.error ?? 'This search failed.')
      } else setResults(saved.results)
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message)
    }
  }

  /** Cancel a running search from the panel. If it already ended, just refresh the list. */
  const cancel = async (id: string) => {
    setCancelError(null)
    try {
      upsertHistory(await cancelSearch(id))
      setEntitiesVersion((version) => version + 1)
    } catch (caught) {
      setCancelError((caught as Error).message)
      listSearches().then(setHistory).catch(console.error)
    }
  }

  /** Delete a finished, failed or cancelled search; if it is open, go back to a new search. */
  const remove = async (id: string) => {
    setDeleteError(null)
    try {
      await deleteSearch(id)
    } catch (caught) {
      setDeleteError((caught as Error).message)
      listSearches().then(setHistory).catch(console.error)
      return
    }
    setHistory((current) => current.filter((entry) => entry.id !== id))
    setEntitiesVersion((version) => version + 1)
    if (shownId.current === id) back()
  }

  /**
   * Searches nobody is watching (started earlier, from another tab, or before a reload)
   * can only be noticed finishing by asking again, so re-list while any of them runs.
   */
  const watched = running ? activeId : null
  const unwatched = history.some((entry) => entry.status === 'running' && entry.id !== watched)
  useEffect(() => {
    if (!unwatched) return
    const timer = window.setInterval(() => {
      listSearches()
        .then((latest) => {
          const finished = latest.some((entry) =>
            historyRef.current.some(
              (known) =>
                known.id === entry.id && known.status === 'running' && entry.status !== 'running',
            ),
          )
          setHistory(latest)
          if (finished) setEntitiesVersion((version) => version + 1)
        })
        .catch(console.error)
    }, SEARCH_POLL_MS)
    return () => window.clearInterval(timer)
  }, [unwatched])

  const saveConfig = async () => {
    const created = await createSearchConfig(draft.current)
    setConfigs((current) => [...current, created])
    setActiveConfigId(created.id)
    return created
  }

  /** Put a saved configuration into the form (remounting it, like the restore on load). */
  const loadConfig = (config: SearchConfig) => {
    touched.current = true
    setForm(config.params)
    draft.current = config.params
    setFormVersion((current) => current + 1)
    setActiveConfigId(config.id)
  }

  const replaceConfig = (updated: SearchConfig) =>
    setConfigs((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)))

  const renameConfig = async (id: string, name: string) =>
    replaceConfig(await updateSearchConfig(id, { name }))

  const overwriteConfig = async (id: string) =>
    replaceConfig(await updateSearchConfig(id, { params: draft.current }))

  const removeConfig = async (id: string) => {
    await deleteSearchConfig(id)
    setConfigs((current) => current.filter((entry) => entry.id !== id))
    setActiveConfigId((current) => (current === id ? null : current))
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
    <div className="flex min-h-svh flex-wrap bg-background-full lg:flex-nowrap">
      <SearchHistory
        searches={history}
        loading={historyLoading}
        error={historyError}
        activeId={activeId}
        user={user}
        onSelect={openSaved}
        onNewSearch={back}
        onCancel={cancel}
        cancelError={cancelError}
        onDelete={remove}
        deleteError={deleteError}
      />
      <div className="min-w-0 flex-1 basis-112">
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
          <Hero
            key={formVersion}
            initial={form}
            onSubmit={search}
            savedResume={savedResume}
            onSavedResumeChange={setSavedResume}
            onChange={(request) => (draft.current = request)}
          />
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
      {view === 'search' && page === 'hero' && (
        <SearchConfigs
          configs={configs}
          loading={configsLoading}
          error={configsError}
          activeId={activeConfigId}
          onSave={saveConfig}
          onLoad={loadConfig}
          onRename={renameConfig}
          onOverwrite={overwriteConfig}
          onDelete={removeConfig}
        />
      )}
    </div>
  )
}
