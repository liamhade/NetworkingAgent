import { useRef, useState } from 'react'
import { streamSearch, type SearchRequest, type SearchResults } from '@/api'
import { Hero } from '@/pages/hero'
import { Results } from '@/pages/results'

const EMPTY_FORM: SearchRequest = { background: '', location: '', looking_for: '' }

export default function App() {
  const [page, setPage] = useState<'hero' | 'results'>('hero')
  const [form, setForm] = useState<SearchRequest>(EMPTY_FORM)
  const [statuses, setStatuses] = useState<string[]>([])
  const [results, setResults] = useState<SearchResults | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const abort = useRef<AbortController | null>(null)

  const search = async (request: SearchRequest) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller

    setForm(request)
    setStatuses([])
    setResults(null)
    setError(null)
    setRunning(true)
    setPage('results')
    window.scrollTo({ top: 0 })

    try {
      await streamSearch(
        request,
        (event) => {
          if (event.type === 'status') setStatuses((current) => [...current, event.message])
          else if (event.type === 'result') setResults(event.data)
          else setError(event.message)
        },
        controller.signal,
      )
    } catch (caught) {
      if (!controller.signal.aborted) setError((caught as Error).message)
    } finally {
      if (abort.current === controller) setRunning(false)
    }
  }

  const back = () => {
    abort.current?.abort()
    setRunning(false)
    setPage('hero')
  }

  return (
    <div className="min-h-svh bg-background-full">
      {page === 'hero' ? (
        <Hero initial={form} onSubmit={search} />
      ) : (
        <Results
          statuses={statuses}
          results={results}
          error={error}
          running={running}
          onBack={back}
        />
      )}
    </div>
  )
}
