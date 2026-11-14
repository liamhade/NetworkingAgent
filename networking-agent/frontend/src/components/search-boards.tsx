import { useEffect, useState } from 'react'
import { RiErrorWarningLine } from '@remixicon/react'
import { getSearchBoards, type BoardInfo, type BoardsConfig, type BoardSetting } from '@/api'
import { Accordion, AccordionItem } from '@/components/base/accordion/accordion'
import { NumberField } from '@/components/base/number-field/number-field'
import { Spinner } from '@/components/base/spinner/spinner'
import { Switch } from '@/components/base/switch/switch'
import { anyBoardOn, clampJobs, resolveBoards } from '@/utils/boards'
import { cx } from '@/utils/cx'

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
 * backend, so adding a board there needs no change here. How results are ranked and ordered
 * stays with the bot.
 */
export function SearchBoards({ value, onChange, onLoaded }: SearchBoardsProps) {
  const [boards, setBoards] = useState<BoardInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  const description = !boards
    ? error
      ? 'Could not load the board list'
      : 'Loading…'
    : `${on} of ${boards.length} boards on`

  return (
    <Accordion variant="separated">
      <AccordionItem title="Search boards" description={description} headingLevel={2}>
        {error ? (
          <p
            role="alert"
            className="flex items-center gap-2 text-body-2-regular text-text-error-primary"
          >
            <RiErrorWarningLine aria-hidden className="size-4" />
            {error}. The search will use the default boards.
          </p>
        ) : !boards || !config ? (
          <p className="flex items-center gap-2 text-body-2-regular text-text-secondary">
            <Spinner size="sm" aria-hidden />
            Loading boards…
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-body-2-regular text-text-secondary">
              Choose where to look and how many jobs to gather from each board. We still decide how
              to rank and sort what we find.
            </p>
            <ul className="flex flex-col divide-y divide-separator-border">
              {boards.map((board) => (
                <BoardRow
                  key={board.id}
                  board={board}
                  setting={config[board.id]}
                  onChange={(change) => update(board, change)}
                />
              ))}
            </ul>
            {!anyBoardOn(config) && (
              <p role="alert" className="text-body-2-regular text-text-error-primary">
                Turn on at least one board to search.
              </p>
            )}
          </div>
        )}
      </AccordionItem>
    </Accordion>
  )
}

interface BoardRowProps {
  board: BoardInfo
  setting: BoardSetting
  onChange: (change: Partial<BoardSetting>) => void
}

function BoardRow({ board, setting, onChange }: BoardRowProps) {
  const unavailable = !board.available
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="flex min-w-0 flex-col gap-1">
        <Switch
          size="sm"
          isSelected={setting.enabled}
          isDisabled={unavailable}
          onChange={(enabled) => onChange({ enabled })}
        >
          {board.label}
        </Switch>
        <p
          className={cx(
            'ps-9 text-body-2-regular',
            unavailable ? 'text-text-tertiary' : 'text-text-secondary',
          )}
        >
          {unavailable ? board.unavailable_reason : board.description}
        </p>
      </div>
      <div className="w-32 shrink-0">
        <NumberField
          size="small"
          aria-label={`Jobs from ${board.label}`}
          value={setting.max_jobs}
          minValue={board.min_jobs}
          maxValue={board.max_jobs}
          isDisabled={unavailable || !setting.enabled}
          onChange={(value) => {
            if (Number.isFinite(value)) onChange({ max_jobs: clampJobs(value, board) })
          }}
        />
      </div>
    </li>
  )
}
