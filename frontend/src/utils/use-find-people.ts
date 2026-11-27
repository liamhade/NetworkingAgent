import { useCallback, useState, useSyncExternalStore } from 'react'
import { type CompanyResult, findPeople } from '@/api'

interface Entry {
  loading: boolean
  error: string | null
}

const IDLE: Entry = { loading: false, error: null }
/** Search state per company, kept only while some card of that company is mounted. */
const entries = new Map<string, Entry>()
const mounted = new Map<string, number>()
const listeners = new Set<() => void>()

function setEntry(key: string, entry: Entry) {
  if (!mounted.has(key)) return
  if (entry === IDLE) entries.delete(key)
  else entries.set(key, entry)
  listeners.forEach((listener) => listener())
}

function subscribe(key: string, listener: () => void) {
  listeners.add(listener)
  mounted.set(key, (mounted.get(key) ?? 0) + 1)
  return () => {
    listeners.delete(listener)
    const left = (mounted.get(key) ?? 1) - 1
    if (left > 0) mounted.set(key, left)
    else {
      mounted.delete(key)
      entries.delete(key)
    }
  }
}

/**
 * One on-demand LinkedIn people search per company: every card of that company shares the
 * same loading and error state, and starting a second search while one runs does nothing.
 * Different companies still search in parallel. `run(sameSchool)` searches; `retry()`
 * repeats the last one.
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
  const key = `${searchId ?? ''}\u0000${companyKey}`
  const entry =
    useSyncExternalStore(
      useCallback((listener: () => void) => subscribe(key, listener), [key]),
      () => entries.get(key),
      () => undefined,
    ) ?? IDLE
  const [lastSameSchool, setLastSameSchool] = useState(false)

  const run = useCallback(
    async (sameSchool = false) => {
      if (!searchId || entries.get(key)?.loading) return
      setLastSameSchool(sameSchool)
      setEntry(key, { loading: true, error: null })
      try {
        const company = await findPeople(searchId, companyKey, jobKey, sameSchool)
        setEntry(key, IDLE)
        onFound(company)
      } catch (caught) {
        setEntry(key, {
          loading: false,
          error: (caught as Error).message || 'Could not find people.',
        })
      }
    },
    [searchId, companyKey, jobKey, key, onFound],
  )

  return {
    loading: entry.loading,
    error: entry.error,
    run,
    retry: () => run(lastSameSchool),
  }
}
