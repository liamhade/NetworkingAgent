import { useEffect, useState } from 'react'
import { Icon } from '@/components/icon'
import { cx } from '@/utils/cx'
import { formatElapsed, LOG_PREVIEW, STAGES, stageOf } from '@/utils/run-progress'

/** Seconds since `startedAt` (ISO), ticking every second; counts from mount without one. */
function useElapsed(startedAt: string | null, ticking: boolean) {
  const [mounted] = useState(() => Date.now())
  const start = startedAt ? Date.parse(startedAt) : mounted
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!ticking) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [ticking])
  return (now - start) / 1000
}

interface RunningProps {
  title: string
  location: string
  /** Labels of the boards being searched. */
  boards: string[]
  /** When the search started (ISO), for the elapsed timer. */
  startedAt: string | null
  /** Progress messages so far, oldest first. */
  statuses: string[]
  /** `running`, or how a search ended without results. */
  state: 'running' | 'cancelled' | 'error'
  /** Why it ended (cancelled / failed). */
  message?: string | null
  /** Cancel the search; absent until the server has given it an id. */
  onCancel?: () => Promise<void> | void
  /** Run the same search again. */
  onRetry: () => void
  /** Back to the search form with these parameters, to edit them first. */
  onEdit: () => void
}

/** A search in progress (or one that was cancelled / failed): stages, live status and log. */
export function Running({
  title,
  location,
  boards,
  startedAt,
  statuses,
  state,
  message,
  onCancel,
  onRetry,
  onEdit,
}: RunningProps) {
  const running = state === 'running'
  const elapsed = useElapsed(startedAt, running)
  const stage = stageOf(statuses)
  const [confirming, setConfirming] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [showAll, setShowAll] = useState(false)

  const latest = statuses.at(-1) ?? 'Starting'
  // While running, the newest message is the live line; the log lists the ones before it.
  const earlier = (running ? statuses.slice(0, -1) : statuses).toReversed()
  const shown = showAll ? earlier : earlier.slice(0, LOG_PREVIEW)

  const cancel = async () => {
    setCancelling(true)
    try {
      await onCancel?.()
    } finally {
      setCancelling(false)
      setConfirming(false)
    }
  }

  return (
    <div className="wrap">
      <div className="crumbs">
        <button type="button" className="crumb-link" onClick={onEdit}>
          Search
        </button>
        <span aria-hidden="true">/</span>
        <span>{running ? 'In progress' : state === 'cancelled' ? 'Cancelled' : 'Failed'}</span>
      </div>
      <div className="head">
        <div>
          <h1>{title}</h1>
          <div className="sub">
            {location && (
              <span>
                <Icon name="pin2" size="sm" />
                {location}
              </span>
            )}
            {boards.length > 0 && (
              <span>
                <Icon name="layers" size="sm" />
                {boards.join(', ')}
              </span>
            )}
          </div>
        </div>
        {!running && (
          <div className="chips">
            <button type="button" className="btn" onClick={onEdit}>
              Edit and re-run
            </button>
            <button type="button" className="btn pri" onClick={onRetry}>
              <Icon name="refresh" />
              Retry search
            </button>
          </div>
        )}
      </div>

      <section className="card run-card" aria-label="Search progress">
        <div className="run-top">
          <div className={cx('orb', !running && 'still')}>
            <Icon name={running ? 'sparkle' : 'alert'} size="lg" />
          </div>
          <div className="t">
            <h2>
              {running
                ? 'Searching job boards and LinkedIn'
                : state === 'cancelled'
                  ? 'Search cancelled'
                  : 'Search failed'}
            </h2>
            <p className={cx('shim', !running && 'still')} aria-live="polite">
              {running ? latest : `Stopped after ${formatElapsed(elapsed)}.`}
            </p>
          </div>
          {running && (
            <div className="elapsed">
              <div className="timer">{formatElapsed(elapsed)}</div>
              <div className="lab">elapsed</div>
            </div>
          )}
          {running &&
            (confirming ? (
              <div className="chips center">
                <b>Stop this search?</b>
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => setConfirming(false)}
                  disabled={cancelling}
                  autoFocus
                >
                  Keep running
                </button>
                <button
                  type="button"
                  className="btn sm danger"
                  onClick={cancel}
                  disabled={cancelling}
                >
                  Yes, cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="btn danger"
                onClick={() => setConfirming(true)}
                disabled={!onCancel}
              >
                <Icon name="stop" />
                Cancel search
              </button>
            ))}
        </div>

        <ol className="steps" aria-label="Search stages">
          {STAGES.map((label, index) => {
            const done = index < stage
            const active = running && index === stage
            return (
              <li key={label} className={cx(done && 'done', active && 'act')}>
                <span className="s">
                  {done && <Icon name="check" size="sm" />}
                  {label}
                </span>
                <span className="sr">{done ? 'complete' : active ? 'in progress' : 'pending'}</span>
              </li>
            )
          })}
        </ol>

        {running ? (
          <div className="notice">
            <Icon name="clock" />
            <span>
              You can leave this page. The agent keeps searching and you will find it under{' '}
              <b>Previous searches</b>. This usually takes a few minutes.
            </span>
          </div>
        ) : (
          <div className="notice err" role="alert">
            <Icon name="alert" />
            <span>{message}</span>
          </div>
        )}

        {earlier.length > 0 && (
          <div>
            <button
              type="button"
              className="disc"
              aria-expanded={showAll}
              aria-controls="run-log"
              onClick={() => setShowAll((current) => !current)}
            >
              {running ? 'Earlier steps' : 'Steps'}{' '}
              <span className="pill neu num">{earlier.length}</span>
              <Icon name="chevron" />
            </button>
            <ul className="live" id="run-log">
              {shown.map((step, index) => (
                <li key={`${earlier.length - index}`}>
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
