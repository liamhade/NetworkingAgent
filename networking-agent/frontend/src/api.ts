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
  /** Stable identity across searches (server-computed); keys the APPLIED toggle. */
  key: string
}

export interface PersonResult {
  name: string
  title: string
  profile_url: string
  alignment: string
  /** Stable identity across searches (server-computed); keys the CONNECTED toggle. */
  key: string
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
  | { type: 'saved'; search: SearchSummary }

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

export interface User {
  id: string
  display_name: string
  created_at: string
}

/** One entry in the search-history side panel. */
export interface SearchSummary {
  id: string
  title: string
  /** ISO-8601 UTC timestamp. */
  created_at: string
}

export interface SavedSearch extends SearchSummary {
  user_id: string
  request: SearchRequest
  results: SearchResults
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

export const getCurrentUser = (signal?: AbortSignal) => getJson<User>('/api/me', signal)

export const listSearches = (signal?: AbortSignal) =>
  getJson<SearchSummary[]>('/api/searches', signal)

export const getSearch = (id: string, signal?: AbortSignal) =>
  getJson<SavedSearch>(`/api/searches/${encodeURIComponent(id)}`, signal)

/** Entities with a toggle: jobs (APPLIED) and people (CONNECTED). */
export type StatusKind = 'job' | 'person'

/** `{kind: {entityKey: active}}`; a missing key means NOT APPLIED / NOT CONNECTED. */
export type StatusMap = Record<StatusKind, Record<string, boolean>>

export const getStatuses = (signal?: AbortSignal) => getJson<StatusMap>('/api/statuses', signal)

export async function setStatus(kind: StatusKind, key: string, active: boolean): Promise<void> {
  const response = await fetch('/api/statuses', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind, key, active }),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
}
