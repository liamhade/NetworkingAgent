import {
  RiAddLine,
  RiCloseCircleLine,
  RiCloseLine,
  RiErrorWarningLine,
  RiHistoryLine,
  RiUserLine,
} from '@remixicon/react'
import type { SearchSummary, User } from '@/api'
import { Button } from '@/components/base/buttons/button'
import { Spinner } from '@/components/base/spinner/spinner'
import { ScrollFade, useScrollFade } from '@/components/foundations/scroll-fade/scroll-fade'
import { cx } from '@/utils/cx'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'

interface SearchHistoryProps {
  searches: SearchSummary[]
  loading: boolean
  error: string | null
  activeId: string | null
  user: User | null
  onSelect: (id: string) => void
  onNewSearch: () => void
  /** Cancel a running search. */
  onCancel: (id: string) => void
  /** Why the last cancel failed (e.g. the search had already finished). */
  cancelError?: string | null
}

/** Left side panel listing the user's previous searches, most recent first. */
export function SearchHistory({
  searches,
  loading,
  error,
  activeId,
  user,
  onSelect,
  onNewSearch,
  onCancel,
  cancelError,
}: SearchHistoryProps) {
  const fade = useScrollFade()

  return (
    <aside
      aria-label="Previous searches"
      className="sticky top-0 hidden h-svh w-72 shrink-0 flex-col border-e border-separator-border bg-background-primary-default md:flex"
    >
      <div className="flex flex-col gap-3 px-4 pt-6 pb-3">
        <h2 className="flex items-center gap-1.5 text-caption-1-semibold text-text-tertiary uppercase">
          <RiHistoryLine aria-hidden className="size-4" />
          Previous searches
        </h2>
        <Button variant="secondary" size="small" leadingIcon={RiAddLine} onClick={onNewSearch}>
          New search
        </Button>
      </div>

      {cancelError && (
        <p
          role="alert"
          className="flex items-start gap-1.5 px-4 pb-2 text-body-2-regular text-text-error-primary"
        >
          <RiErrorWarningLine aria-hidden className="mt-0.5 size-4 shrink-0" />
          {cancelError}
        </p>
      )}

      <div className="relative min-h-0 flex-1">
        <div onScroll={fade.onScroll} className="h-full overflow-y-auto px-3 pb-4">
          {loading && searches.length === 0 ? (
            <div className="flex items-center gap-2 px-1 py-2 text-body-2-regular text-text-tertiary">
              <Spinner />
              Loading…
            </div>
          ) : error ? (
            <p
              role="alert"
              className="flex items-start gap-1.5 px-1 py-2 text-body-2-regular text-text-error-primary"
            >
              <RiErrorWarningLine aria-hidden className="mt-0.5 size-4 shrink-0" />
              {error}
            </p>
          ) : searches.length === 0 ? (
            <p className="px-1 py-2 text-body-2-regular text-text-tertiary">
              Your searches will show up here.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {searches.map((search) => (
                <li key={search.id}>
                  <HistoryBubble
                    search={search}
                    active={search.id === activeId}
                    onSelect={() => onSelect(search.id)}
                    onCancel={() => onCancel(search.id)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
        <ScrollFade progress={fade.progress} surfaceClassName="from-background-primary-default" />
      </div>

      {user && (
        <div className="flex items-center gap-2 border-t border-separator-border px-4 py-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-background-secondary-default text-foreground-icon-secondary">
            <RiUserLine aria-hidden className="size-4" />
          </span>
          <span className="truncate text-body-2-medium text-text-secondary">
            {user.display_name}
          </span>
        </div>
      )}
    </aside>
  )
}

function HistoryBubble({
  search,
  active,
  onSelect,
  onCancel,
}: {
  search: SearchSummary
  active: boolean
  onSelect: () => void
  onCancel: () => void
}) {
  const created = new Date(search.created_at)
  const running = search.status === 'running'
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? 'true' : undefined}
        className={cx(
          'flex w-full cursor-pointer flex-col gap-0.5 rounded-2xl rounded-ss-md border px-3 py-2.5 text-start transition-colors',
          'outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
          running && 'pe-20',
          active
            ? 'border-border-button-active bg-background-primary-active'
            : 'border-border-button-default bg-background-primary-default hover:border-border-button-hover hover:bg-background-primary-hover',
        )}
      >
        <span className="line-clamp-2 text-body-2-medium text-text-primary">{search.title}</span>
        <span className="flex items-center gap-1.5 text-caption-1-medium text-text-tertiary">
          {running ? (
            <>
              <Spinner size="xs" aria-label="Search in progress" />
              Searching…
            </>
          ) : search.status === 'error' ? (
            <>
              <RiErrorWarningLine aria-hidden className="size-3.5 text-text-error-primary" />
              Failed
            </>
          ) : search.status === 'cancelled' ? (
            <>
              <RiCloseCircleLine aria-hidden className="size-3.5 text-foreground-icon-tertiary" />
              Cancelled
            </>
          ) : null}
          {search.status !== 'done' && <span aria-hidden>·</span>}
          <time dateTime={search.created_at} title={fullDateFormat.format(created)}>
            {formatRelativeDate(created)}
          </time>
        </span>
      </button>
      {running && (
        <Button
          variant="ghost"
          size="xs"
          leadingIcon={RiCloseLine}
          onClick={onCancel}
          aria-label={`Cancel search: ${search.title}`}
          className="absolute end-2 top-2"
        >
          Cancel
        </Button>
      )}
    </div>
  )
}
