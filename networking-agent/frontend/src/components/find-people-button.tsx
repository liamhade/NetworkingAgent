import { useState } from 'react'
import { type CompanyResult, findPeople } from '@/api'
import { Icon } from '@/components/icon'

interface FindPeopleButtonProps {
  /** Saved search the company belongs to; the button is disabled until it is saved. */
  searchId: string | null
  companyKey: string
  /** Search for people around this job (its title becomes the first keyword set). */
  jobKey?: string
  /** Names the target for screen readers, e.g. "Acme" or "Data Analyst at Acme". */
  target: string
  label: string
  /** `button`: a small bordered button (pane footers); `link`: an inline cross-link. */
  variant?: 'button' | 'link'
  onFound: (company: CompanyResult) => void
}

/**
 * One on-demand LinkedIn people search. Every button keeps its own loading and error
 * state, so several can run at once.
 */
export function FindPeopleButton({
  searchId,
  companyKey,
  jobKey,
  target,
  label,
  variant = 'button',
  onFound,
}: FindPeopleButtonProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    if (!searchId) return
    setLoading(true)
    setError(null)
    try {
      onFound(await findPeople(searchId, companyKey, jobKey))
    } catch (caught) {
      setError((caught as Error).message || 'Could not find people.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className={variant === 'link' ? 'xlink per' : 'btn sm'}
        disabled={!searchId || loading}
        aria-busy={loading}
        aria-label={`${label}: ${target}`}
        title={searchId ? undefined : 'Available once the search is saved'}
        onClick={run}
      >
        {loading ? <span className="spin" aria-hidden="true" /> : <Icon name="users" />}
        {loading ? 'Searching LinkedIn…' : label}
      </button>
      {loading && variant === 'button' && (
        <span className="find-hint">
          Usually 1 to 2 minutes
        </span>
      )}
      {error && (
        <span role="alert" className="inline-err">
          {error}
          <button type="button" className="btn xs" onClick={run}>
            Retry
          </button>
        </span>
      )}
    </>
  )
}
