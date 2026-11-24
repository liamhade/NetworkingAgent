import type { BoardInfo, BoardsConfig, BoardSetting } from '@/api'

export const clampJobs = (value: number, board: BoardInfo) =>
  Math.max(board.min_jobs, Math.min(board.max_jobs, Math.round(value)))

/**
 * The full config for `boards`: what the user set, else each board's default. Out-of-range
 * limits are clamped, and an unavailable board is never on (the server ignores it anyway).
 */
export function resolveBoards(boards: BoardInfo[], value?: BoardsConfig): BoardsConfig {
  return Object.fromEntries(
    boards.map((board) => {
      const given = value?.[board.id] ?? board.default
      const setting: BoardSetting = {
        enabled: board.available && given.enabled,
        max_jobs: clampJobs(given.max_jobs, board),
      }
      return [board.id, setting]
    }),
  )
}

/** True when at least one board will be searched. */
export const anyBoardOn = (config: BoardsConfig) =>
  Object.values(config).some((setting) => setting.enabled)
