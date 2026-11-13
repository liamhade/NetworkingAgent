import { RiRefreshLine, RiUserSearchLine } from '@remixicon/react'
import { useState } from 'react'
import { type CompanyResult, findPeople } from '@/api'
import { Button } from '@/components/base/buttons/button'
import { SpinnerGlyph } from '@/components/base/spinner/spinner'

interface FindPeopleButtonProps {
  /** Saved search the company belongs to; the button is disabled until it is saved. */
  searchId: string | null
  companyKey: string
  /** Search for people around this job (its title becomes the first keyword set). */
  jobKey?: string
  /** Names the target for screen readers, e.g. "Acme" or "Data Analyst at Acme". */
  target: string
  label?: string
  onFound: (company: CompanyResult) => void
}

/**
 * "Find People To Connect With": one on-demand people search. Every button keeps its own
 * loading and error state, so several can run at once.
 */
export function FindPeopleButton({
  searchId,
  companyKey,
  jobKey,
  target,
  label = 'Find People To Connect With',
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
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="secondary"
        size="xs"
        leadingIcon={loading ? undefined : RiUserSearchLine}
        disabled={!searchId || loading}
        aria-busy={loading}
        aria-label={`${label}: ${target}`}
        title={searchId ? undefined : 'Available once the search is saved'}
        onClick={run}
      >
        {loading && <SpinnerGlyph size="xs" className="me-1" />}
        {loading ? 'Finding people…' : label}
      </Button>
      {error && (
        <span role="alert" className="flex items-center gap-1 text-caption-1-medium text-text-error-primary">
          {error}
          <Button variant="ghost" size="xs" leadingIcon={RiRefreshLine} onClick={run}>
            Retry
          </Button>
        </span>
      )}
    </div>
  )
}
