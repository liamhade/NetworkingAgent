/** Client for the FastAPI backend (see backend/src/server.py and schemas.py). */

/** One board in a search: on or off, and the most jobs to gather from it. */
export interface BoardSetting {
  enabled: boolean
  max_jobs: number
}

/** `{board_id: setting}`: the self-contained boards config a search carries. */
export type BoardsConfig = Record<string, BoardSetting>

/** A job board as `GET /api/search/boards` describes it (the single source of truth). */
export interface BoardInfo {
  id: string
  label: string
  description: string
  /** False when the board can't run right now (e.g. USAJOBS without an API key). */
  available: boolean
  unavailable_reason: string
  default: BoardSetting
  min_jobs: number
  max_jobs: number
}

export interface SearchRequest {
  background: string
  location: string
  looking_for: string
  /** Boards to search; leave out for the server's defaults (older searches have none). */
  boards?: BoardsConfig
}

export type ResumeProfile = Pick<SearchRequest, 'background' | 'location' | 'looking_for'>

export interface JobResult {
  title: string
  url: string
  location: string
  salary: string
  alignment: string
  /** Fit with the user's profile, 0-100 (server-computed); absent on older searches. */
  score?: number | null
  /** Stable identity across searches (server-computed); keys the APPLIED toggle. */
  key: string
}

export interface PersonResult {
  name: string
  title: string
  profile_url: string
  alignment: string
  /** Example LinkedIn connection note (server caps its length); absent on older searches. */
  connect_message?: string
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
  /** Fit with the user's profile, 0-100; results come sorted by it. Absent on older searches. */
  score?: number | null
  /**
   * True once a people search ran for this company, so an empty `people` means "no one
   * found" rather than "not searched yet". Only the top companies are searched during a
   * search; the rest on demand (`findPeople`).
   */
  people_searched?: boolean
  /** Stable identity across searches (server-computed); keys the pin. Absent if unkeyed. */
  key?: string
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

export const getSearchBoards = (signal?: AbortSignal) =>
  getJson<BoardInfo[]>('/api/search/boards', signal)

export const listSearches = (signal?: AbortSignal) =>
  getJson<SearchSummary[]>('/api/searches', signal)

/**
 * Find people to connect with at one company of a saved search, optionally for one of its
 * jobs. The server saves them into the search and returns the updated company. Several
 * calls can run at once.
 */
export async function findPeople(
  searchId: string,
  companyKey: string,
  jobKey?: string,
): Promise<CompanyResult> {
  const response = await fetch(`/api/searches/${encodeURIComponent(searchId)}/people`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_key: companyKey, job_key: jobKey ?? null }),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

export const getSearch =(id: string, signal?: AbortSignal) =>
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

/** Entities that can be pinned to come back to later. */
export type PinKind = 'company' | 'job' | 'person'

/** `{kind: {entityKey: pinned}}`; a missing key means not pinned. */
export type PinMap = Record<PinKind, Record<string, boolean>>

export const getPins = (signal?: AbortSignal) => getJson<PinMap>('/api/pins', signal)

export async function setPin(kind: PinKind, key: string, pinned: boolean): Promise<void> {
  const response = await fetch('/api/pins', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind, key, pinned }),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/** Where and when an entity was seen across the user's searches. */
export interface Sighting {
  /** Entity key; matches `key` in search results (and the status / pin maps). */
  key: string
  /** ISO-8601 UTC timestamps of the oldest / newest search it appeared in. */
  first_seen: string
  last_seen: string
  /** Searches it appeared in, most recent first. */
  searches: SearchSummary[]
}

export interface CompanyEntity extends Sighting {
  name: string
  url: string
  description: string
  alignment: string
  job_count: number
  person_count: number
}

export interface JobEntity extends Sighting {
  title: string
  url: string
  location: string
  salary: string
  alignment: string
  company: string
  company_key: string
}

export interface PersonEntity extends Sighting {
  name: string
  title: string
  profile_url: string
  alignment: string
  /** Example LinkedIn connection note (server caps its length); absent on older searches. */
  connect_message?: string
  company: string
  company_key: string
}

export interface EntityMap {
  companies: CompanyEntity
  jobs: JobEntity
  people: PersonEntity
}

export type EntityKind = keyof EntityMap

/** Everything of one kind seen across the user's searches, most recently seen first. */
export const listEntities = <K extends EntityKind>(kind: K, signal?: AbortSignal) =>
  getJson<EntityMap[K][]>(`/api/entities/${kind}`, signal)
