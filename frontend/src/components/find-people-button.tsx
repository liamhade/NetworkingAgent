import { useId, useState, type FormEvent } from 'react'
import type { CompanyResult } from '@/api'
import { Icon } from '@/components/icon'
import { useFindPeople } from '@/utils/use-find-people'

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
  const { loading, error, run, retry } = useFindPeople({ searchId, companyKey, jobKey, onFound })
  return (
    <>
      <FindButton
        loading={loading}
        disabled={!searchId}
        variant={variant}
        label={label}
        target={target}
        onClick={() => run()}
      />
      {loading && variant === 'button' && (
        <span className="find-hint">Usually 1 to 2 minutes</span>
      )}
      {error && <FindError message={error} onRetry={retry} />}
    </>
  )
}

/**
 * The people pane's footer search: type criteria ("people who went to my school",
 * "recruiters in Boston") and search, or leave it empty for the usual search.
 */
export function FindPeopleSearch({
  searchId,
  companyKey,
  target,
  label,
  onFound,
}: Omit<FindPeopleButtonProps, 'jobKey' | 'variant'>) {
  const [query, setQuery] = useState('')
  const inputId = useId()
  const { loading, error, run, retry } = useFindPeople({ searchId, companyKey, onFound })
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!searchId || loading) return
    void run(query)
  }
  return (
    <form
      className="find-people"
      role="search"
      aria-label={`Find people at ${target}`}
      onSubmit={submit}
    >
      <label className="sr" htmlFor={inputId}>
        Who to look for at {target}
      </label>
      <input
        id={inputId}
        type="search"
        value={query}
        maxLength={300}
        placeholder="e.g. went to my school, recruiters"
        disabled={!searchId || loading}
        onChange={(event) => setQuery(event.target.value)}
      />
      <FindButton
        type="submit"
        loading={loading}
        disabled={!searchId}
        variant="button"
        label={label}
        target={target}
      />
      {loading && <span className="find-hint">Usually 1 to 2 minutes</span>}
      {error && <FindError message={error} onRetry={retry} />}
    </form>
  )
}

function FindButton({
  type = 'button',
  loading,
  disabled,
  variant,
  label,
  target,
  onClick,
}: {
  type?: 'button' | 'submit'
  loading: boolean
  disabled: boolean
  variant: 'button' | 'link'
  label: string
  target: string
  onClick?: () => void
}) {
  return (
    <button
      type={type}
      className={variant === 'link' ? 'xlink per' : 'btn sm'}
      disabled={disabled || loading}
      aria-busy={loading}
      aria-label={`${label}: ${target}`}
      title={disabled ? 'Available once the search is saved' : undefined}
      onClick={onClick}
    >
      {loading ? <span className="spin" aria-hidden="true" /> : <Icon name="users" />}
      {loading ? 'Searching LinkedIn…' : label}
    </button>
  )
}

function FindError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <span role="alert" className="inline-err">
      {message}
      <button type="button" className="btn xs" onClick={onRetry}>
        Retry
      </button>
    </span>
  )
}
