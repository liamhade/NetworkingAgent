import { useEffect, useRef, useState } from 'react'
import {
  getCurrentUser,
  getSearch,
  getStatuses,
  listSearches,
  setStatus,
  streamSearch,
  type SearchRequest,
  type SearchResults,
  type SearchSummary,
  type StatusKind,
  type StatusMap,
  type User,
} from '@/api'
import { SearchHistory } from '@/components/search-history'
import { Hero } from '@/pages/hero'
import { Results } from '@/pages/results'

const EMPTY_FORM: SearchRequest = { background: '', location: '', looking_for: '' }
const EMPTY_STATUSES: StatusMap = { job: {}, person: {} }

export default function App() {
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

  const [entityStatuses, setEntityStatuses] = useState<StatusMap>(EMPTY_STATUSES)
  const [statusError, setStatusError] = useState<string | null>(null)
  /** Latest change per entity, so a stale failed request doesn't roll back a newer one. */
  const statusVersions = useRef(new Map<string, number>())

  useEffect(() => {
    const controller = new AbortController()
    getCurrentUser(controller.signal)
      .then(setUser)
      .catch(() => {
        // The name is cosmetic; the panel works without it.
      })
    listSearches(controller.signal)
      .then((searches) => {
        setHistory(searches)
        setHistoryError(null)
      })
      .catch((caught: Error) => {
        if (!controller.signal.aborted) setHistoryError('Could not load previous searches.')
        console.error(caught)
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false)
      })
    getStatuses(controller.signal)
      .then((loaded) => setEntityStatuses({ ...EMPTY_STATUSES, ...loaded }))
      .catch((caught: Error) => {
        if (!controller.signal.aborted) setStatusError('Could not load APPLIED / CONNECTED marks.')
        console.error(caught)
      })
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

  /** Optimistically flip a job/person toggle; roll back if saving fails. */
  const toggleStatus = async (kind: StatusKind, key: string, active: boolean) => {
    const previous = entityStatuses[kind][key] ?? false
    const versionKey = `${kind}:${key}`
    const version = (statusVersions.current.get(versionKey) ?? 0) + 1
    statusVersions.current.set(versionKey, version)
    const apply = (value: boolean) =>
      setEntityStatuses((current) => ({ ...current, [kind]: { ...current[kind], [key]: value } }))

    apply(active)
    try {
      await setStatus(kind, key, active)
      if (statusVersions.current.get(versionKey) === version) setStatusError(null)
    } catch (caught) {
      console.error(caught)
      if (statusVersions.current.get(versionKey) !== version) return
      apply(previous)
      setStatusError('Could not save that change. Please try again.')
    }
  }

  const back = () => {
    abort.current?.abort()
    setRunning(false)
    setActiveId(null)
    setPage('hero')
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
        {page === 'hero' ? (
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
            onBack={back}
          />
        )}
      </div>
    </div>
  )
}
