/** The pipeline's stages, in the order the backend reports them. */
export const STAGES = [
  'Understand profile',
  'Find jobs',
  'Rank companies',
  'Find people',
  'Write notes',
] as const

/** Which stage the backend is in, from its progress messages (see backend/src/pipeline/steps.py). */
export function stageOf(statuses: readonly string[]): number {
  let stage = 0
  for (const message of statuses) {
    if (/^Planning/.test(message)) stage = Math.max(stage, 1)
    else if (/^(Ranking companies|Top companies)/.test(message)) stage = Math.max(stage, 2)
    else if (/^Looking for |current employees? found/.test(message)) stage = Math.max(stage, 3)
    else if (/^Compiling/.test(message)) stage = Math.max(stage, 4)
  }
  return stage
}

/** Progress messages shown before "Latest steps" is expanded. */
export const LOG_PREVIEW = 3

const pad = (value: number) => String(value).padStart(2, '0')

export function formatElapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(s / 3600)
  const clock = `${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`
  return hours ? `${hours}:${clock}` : clock
}
