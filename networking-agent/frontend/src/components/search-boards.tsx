import { useEffect, useId, useState } from 'react'
import { getSearchBoards, type BoardInfo, type BoardsConfig, type BoardSetting } from '@/api'
import { Icon } from '@/components/icon'
import { anyBoardOn, clampJobs, resolveBoards } from '@/utils/boards'

interface SearchBoardsProps {
  /** The search's boards config; undefined = every board's default. */
  value?: BoardsConfig
  onChange: (config: BoardsConfig) => void
  /** Reports the board list once loaded (null while loading or if it failed). */
  onLoaded?: (config: BoardsConfig | null) => void
}

/**
 * Collapsible "Search boards" panel: which job boards the search uses and how many jobs to
 * gather from each. The board list (labels, defaults, limits, availability) comes from the
 * backend, so adding a board there needs no change here. Ranking stays with the bot.
 */
export function SearchBoards({ value, onChange, onLoaded }: SearchBoardsProps) {
  const [boards, setBoards] = useState<BoardInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const panelId = useId()

  useEffect(() => {
    const controller = new AbortController()
    getSearchBoards(controller.signal)
      .then(setBoards)
      .catch((caught: Error) => {
        if (!controller.signal.aborted) setError(caught.message)
      })
    return () => controller.abort()
  }, [])

  const config = boards ? resolveBoards(boards, value) : null

  useEffect(() => {
    onLoaded?.(config)
    // `config` is rebuilt every render; its content only changes with `boards` or `value`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boards, value])

  const update = (board: BoardInfo, change: Partial<BoardSetting>) => {
    if (!config) return
    onChange({ ...config, [board.id]: { ...config[board.id], ...change } })
  }

  const on = config ? Object.values(config).filter((setting) => setting.enabled).length : 0
  const summary = !boards
    ? error
      ? 'Could not load the board list'
      : 'Loading…'
    : `${on} of ${boards.length} boards on`

  return (
    <div className="boards">
      <button
        type="button"
        className="sum"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        <Icon name="layers" />
        Search boards
        <span className="pill neu num">{summary}</span>
        <Icon name="chevron" />
      </button>
      {open && (
        <div id={panelId}>
          {error ? (
            <p role="alert" className="warn">
              {error}. The search will use the default boards.
            </p>
          ) : !boards || !config ? (
            <p className="loading">
              <span className="spin" aria-hidden="true" />
              Loading boards…
            </p>
          ) : (
            <>
              <p className="intro">
                Choose where to look and how many jobs to gather from each board. The agent still
                ranks and sorts what it finds.
              </p>
              {boards.map((board) => (
                <BoardRow
                  key={board.id}
                  board={board}
                  setting={config[board.id]}
                  onChange={(change) => update(board, change)}
                />
              ))}
              {!anyBoardOn(config) && (
                <p role="alert" className="warn">
                  Turn on at least one board to search.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

interface BoardRowProps {
  board: BoardInfo
  setting: BoardSetting
  onChange: (change: Partial<BoardSetting>) => void
}

function BoardRow({ board, setting, onChange }: BoardRowProps) {
  const id = useId()
  const unavailable = !board.available
  // What the user is typing (null: not editing, show the saved limit); committed and
  // clamped on blur or Enter.
  const [typed, setTyped] = useState<string | null>(null)
  const text = typed ?? String(setting.max_jobs)

  const commit = () => {
    setTyped(null)
    const parsed = Number.parseInt(text, 10)
    if (!Number.isFinite(parsed)) return
    const clamped = clampJobs(parsed, board)
    if (clamped !== setting.max_jobs) onChange({ max_jobs: clamped })
  }

  return (
    <div className="board">
      <label className="sw">
        <input
          type="checkbox"
          role="switch"
          checked={setting.enabled}
          disabled={unavailable}
          aria-labelledby={`${id}-name`}
          aria-describedby={`${id}-desc`}
          onChange={(event) => onChange({ enabled: event.target.checked })}
        />
        <i />
      </label>
      <div>
        <b id={`${id}-name`}>{board.label}</b>
        <div className="d" id={`${id}-desc`}>
          {board.description}
        </div>
        {unavailable && <div className="why">{board.unavailable_reason}</div>}
      </div>
      <div className="num-wrap">
        <input
          className="num-in num"
          type="text"
          inputMode="numeric"
          aria-label={`Jobs from ${board.label}`}
          value={text}
          disabled={unavailable || !setting.enabled}
          onChange={(event) => setTyped(event.target.value.replace(/[^\d]/g, ''))}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              commit()
            }
          }}
        />
        <span className="d"> max jobs</span>
      </div>
    </div>
  )
}
