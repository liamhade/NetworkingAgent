/** Client for the FastAPI backend (see backend/src/server.py and schemas.py). */

export interface SearchRequest {
  background: string
  location: string
  looking_for: string
}

export type ResumeProfile = SearchRequest

export interface JobResult {
  title: string
  url: string
  location: string
  salary: string
  alignment: string
}

export interface PersonResult {
  name: string
  title: string
  profile_url: string
  alignment: string
}

export interface CompanyResult {
  name: string
  url: string
  description: string
  alignment: string
  jobs: JobResult[]
  people: PersonResult[]
}

export interface SearchResults {
  summary: string
  companies: CompanyResult[]
}

export type AgentEvent =
  | { type: 'status'; message: string }
  | { type: 'result'; data: SearchResults }
  | { type: 'error'; message: string }

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Not JSON; fall through.
  }
  return `Request failed (${response.status})`
}

export async function parseResume(file: File): Promise<ResumeProfile> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/resume', { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

/** Run the agent, calling `onEvent` for every Server-Sent Event it streams back. */
export async function streamSearch(
  request: SearchRequest,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok || !response.body) throw new Error(await errorMessage(response))

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const data = chunk
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      if (data) onEvent(JSON.parse(data) as AgentEvent)
    }
  }
}
