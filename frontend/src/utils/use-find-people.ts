import { useState } from 'react'
import { type CompanyResult, findPeople } from '@/api'

/**
 * One on-demand LinkedIn people search with its own loading and error state, so several
 * can run at once. `run(query)` searches; `retry()` repeats the last one.
 */
export function useFindPeople({
  searchId,
  companyKey,
  jobKey,
  onFound,
}: {
  searchId: string | null
  companyKey: string
  jobKey?: string
  onFound: (company: CompanyResult) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState<string | undefined>()

  const run = async (query?: string) => {
    if (!searchId) return
    setLoading(true)
    setError(null)
    setLastQuery(query)
    try {
      onFound(await findPeople(searchId, companyKey, jobKey, query))
    } catch (caught) {
      setError((caught as Error).message || 'Could not find people.')
    } finally {
      setLoading(false)
    }
  }

  return { loading, error, run, retry: () => run(lastQuery) }
}
