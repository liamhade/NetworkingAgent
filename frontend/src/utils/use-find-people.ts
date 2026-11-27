import { useState } from 'react'
import { type CompanyResult, findPeople } from '@/api'

/**
 * One on-demand LinkedIn people search with its own loading and error state, so several
 * can run at once. `run(sameSchool)` searches; `retry()` repeats the last one.
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
  const [lastSameSchool, setLastSameSchool] = useState(false)

  const run = async (sameSchool = false) => {
    if (!searchId) return
    setLoading(true)
    setError(null)
    setLastSameSchool(sameSchool)
    try {
      onFound(await findPeople(searchId, companyKey, jobKey, sameSchool))
    } catch (caught) {
      setError((caught as Error).message || 'Could not find people.')
    } finally {
      setLoading(false)
    }
  }

  return { loading, error, run, retry: () => run(lastSameSchool) }
}
