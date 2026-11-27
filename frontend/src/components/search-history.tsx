import { useState } from 'react'
import type { SearchStatus, SearchSummary } from '@/api'
import { Icon } from '@/components/icon'
import { cx } from '@/utils/cx'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'

interface SearchHistoryProps {
  searches: SearchSummary[]
  loading: boolean
  error: string | null
  activeId: string | null
  onSelect: (id: string) => void
  onNewSearch: () => void
  /** Cancel a running search. */
  onCancel: (id: string) => void
  /** Why the last cancel failed (e.g. the search had already finished). */
  cancelError?: string | null
  /** Delete a search that is not running (the panel asks for confirmation first). */
  onDelete: (id: string) => Promise<void>
  /** Why the last delete failed. */
  deleteError?: string | null
  /** Small screens: the sidebar slides in as a drawer. */
  open?: boolean
}

const DOT: Record<SearchStatus, string> = { done: '', running: 'run', error: 'err', cancelled: 'can' }
const STATUS_LABEL: Record<SearchStatus, string> = {
  done: 'Done',
  running: 'Searching',
  error: 'Failed',
  cancelled: 'Cancelled',
}

/** Left sidebar: "New search" and the user's previous searches, most recent first. */
export function SearchHistory({
  searches,
  loading,
  error,
  activeId,
  onSelect,
  onNewSearch,
  onCancel,
  cancelError,
  onDelete,
  deleteError,
  open = false,
}: SearchHistoryProps) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  return (
    <aside className={cx('side', open && 'open')} id="side" aria-label="Previous searches">
      <button type="button" className="btn pri" onClick={onNewSearch}>
        <Icon name="plus" /> New search
      </button>
      <h2>Previous searches</h2>

      {[cancelError, deleteError].map(
        (message) =>
          message && (
            <p key={message} role="alert" className="alert">
              <Icon name="alert" size="sm" />
              {message}
            </p>
          ),
      )}

      {loading && searches.length === 0 ? (
        <p className="msg loading">
          <span className="spin" aria-hidden="true" />
          Loading…
        </p>
      ) : error ? (
        <p role="alert" className="alert">
          <Icon name="alert" size="sm" />
          {error}
        </p>
      ) : searches.length === 0 ? (
        <p className="msg">Your searches will show up here.</p>
      ) : (
        <ul className="hist">
          {searches.map((search) => (
            <HistoryItem
              key={search.id}
              search={search}
              active={search.id === activeId}
              onSelect={() => onSelect(search.id)}
              onCancel={() => onCancel(search.id)}
              confirming={confirmingId === search.id}
              deleting={deletingId === search.id}
              onAskDelete={() => setConfirmingId(search.id)}
              onKeep={() => setConfirmingId(null)}
              onDelete={async () => {
                setDeletingId(search.id)
                try {
                  await onDelete(search.id)
                } finally {
                  setDeletingId(null)
                  setConfirmingId(null)
                }
              }}
            />
          ))}
        </ul>
      )}
    </aside>
  )
}

function HistoryItem({
  search,
  active,
  onSelect,
  onCancel,
  confirming,
  deleting,
  onAskDelete,
  onKeep,
  onDelete,
}: {
  search: SearchSummary
  active: boolean
  onSelect: () => void
  onCancel: () => void
  confirming: boolean
  deleting: boolean
  onAskDelete: () => void
  onKeep: () => void
  onDelete: () => void
}) {
  const created = new Date(search.created_at)
  const running = search.status === 'running'
  const ended = search.status === 'error' || search.status === 'cancelled'
  return (
    <li>
      <button
        type="button"
        className="h"
        onClick={onSelect}
        aria-current={active ? 'page' : undefined}
      >
        <span className="t">{search.title}</span>
        <span className="m">
          <span className={cx('dot', DOT[search.status])} aria-hidden="true" />
          {running ? (
            <span>Searching…</span>
          ) : (
            <>
              {ended && (
                <>
                  <span>{STATUS_LABEL[search.status]}</span>
                  <span aria-hidden="true">·</span>
                </>
              )}
              <time dateTime={search.created_at} title={fullDateFormat.format(created)}>
                {formatRelativeDate(created)}
              </time>
            </>
          )}
          <span className="sr">Status: {STATUS_LABEL[search.status]}</span>
        </span>
      </button>
      {running ? (
        <button
          type="button"
          className="x stop"
          onClick={onCancel}
          aria-label={`Cancel search: ${search.title}`}
          title="Cancel search"
        >
          <Icon name="stop" size="sm" />
        </button>
      ) : (
        <button
          type="button"
          className="x"
          onClick={onAskDelete}
          aria-label={`Delete search: ${search.title}`}
          title="Delete search"
        >
          <Icon name="trash" size="sm" />
        </button>
      )}
      {confirming && !running && (
        <div className="confirm">
          <span>Delete this search?</span>
          <button type="button" className="btn xs" onClick={onKeep} disabled={deleting}>
            Keep
          </button>
          <button
            type="button"
            className="btn xs danger"
            onClick={onDelete}
            disabled={deleting}
            aria-label={`Confirm delete search: ${search.title}`}
          >
            Delete
          </button>
        </div>
      )}
    </li>
  )
}
