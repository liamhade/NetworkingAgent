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
  /** Schools attended, most relevant first; used to find people with the same school. */
  education?: string[]
  /** Boards to search; leave out for the server's defaults (older searches have none). */
  boards?: BoardsConfig
}

export type ResumeProfile = Pick<
  SearchRequest,
  'background' | 'location' | 'looking_for' | 'education'
>

/**
 * The search parameters as saved for the user (`GET`/`PUT /api/search/params`): a
 * `SearchRequest` whose text fields may be empty (a draft). Boards come back normalized.
 */
export type SearchParams = SearchRequest

/** The user's saved resume (`GET /api/resume/saved`); the PDF itself is at `savedResumeUrl`. */
export interface SavedResume {
  filename: string
  /** Bytes of the original PDF. */
  size: number
  /** Bytes stored after compression. */
  stored_size: number
  /** ISO-8601 UTC timestamp. */
  uploaded_at: string
  profile: ResumeProfile
}

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
  /** What you share with them, e.g. "Same school: Cornell"; absent when nothing was found. */
  shared_background?: string
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
  /** The search was cancelled; the last event of its stream. */
  | { type: 'cancelled'; search: SearchSummary }
  /** First event of a search stream: the saved (still running) search, so its id is known. */
  | { type: 'started'; search: SearchSummary }

/** Fired on `window` when the API says the session is gone (401), so the app can sign in again. */
export const UNAUTHORIZED_EVENT = 'na:unauthorized'

/** `fetch` for `/api` calls: a 401 (outside `/api/auth`) means "signed out". */
async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init)
  if (response.status === 401 && !input.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  return response
}

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
  const response = await apiFetch('/api/resume', { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

/** Download link for the saved resume PDF. */
export const savedResumeUrl = '/api/resume/saved/file'

/** The saved resume, or null when none was uploaded yet. */
export const getSavedResume = (signal?: AbortSignal) =>
  getJson<SavedResume | null>('/api/resume/saved', signal)

export async function deleteSavedResume(): Promise<void> {
  const response = await apiFetch('/api/resume/saved', { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/** The last saved search parameters, or null when none were saved yet. */
export const getSearchParams = (signal?: AbortSignal) =>
  getJson<SearchParams | null>('/api/search/params', signal)

export async function saveSearchParams(params: SearchParams): Promise<SearchParams> {
  const response = await apiFetch('/api/search/params', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

/** A named, saved search configuration (`/api/search/configs`); `params` is a `SearchParams`. */
export interface SearchConfig {
  id: string
  name: string
  params: SearchParams
  /** ISO-8601 UTC timestamps. */
  created_at: string
  updated_at: string
}

export const listSearchConfigs = (signal?: AbortSignal) =>
  getJson<SearchConfig[]>('/api/search/configs', signal)

async function sendJson<T>(url: string, method: string, body: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

/** Save `params`; without a name the server picks "Search Configuration #n". */
export const createSearchConfig = (params: SearchParams, name?: string) =>
  sendJson<SearchConfig>(
    '/api/search/configs',
    'POST',
    name === undefined ? { params } : { params, name },
  )

/** Rename a configuration and/or overwrite its parameters. */
export const updateSearchConfig = (id: string, changes: { name?: string; params?: SearchParams }) =>
  sendJson<SearchConfig>(`/api/search/configs/${encodeURIComponent(id)}`, 'PATCH', changes)

export async function deleteSearchConfig(id: string): Promise<void> {
  const response = await apiFetch(`/api/search/configs/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/** Read a Server-Sent Events response, calling `onEvent` for every event in it. */
async function readEvents(
  response: Response,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
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

/**
 * Start a search and call `onEvent` for every Server-Sent Event it streams back. The search
 * runs on the server regardless of this stream: closing or aborting it does not stop it
 * (follow it again with `streamSearchEvents`).
 */
export async function streamSearch(
  request: SearchRequest,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  await readEvents(response, onEvent)
}

/**
 * Follow a search that is already running (or finished) from its first progress message,
 * until it ends.
 */
export async function streamSearchEvents(
  id: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch(`/api/searches/${encodeURIComponent(id)}/events`, { signal })
  await readEvents(response, onEvent)
}

export interface User {
  id: string
  display_name: string
  created_at: string
}

/** `running`: still searching in the background; `error`: failed or interrupted. */
export type SearchStatus = 'running' | 'done' | 'error' | 'cancelled'

/** One entry in the search-history side panel. */
export interface SearchSummary {
  id: string
  title: string
  /** ISO-8601 UTC timestamp. */
  created_at: string
  status: SearchStatus
}

export interface SavedSearch extends SearchSummary {
  user_id: string
  request: SearchRequest
  /** Empty until the search is done. */
  results: SearchResults
  /** Progress messages so far. */
  messages: string[]
  /** Why the search failed (status `error`). */
  error: string | null
}

/** Cancel a running search (the server refuses with 409 if it already ended). */
export async function cancelSearch(id: string): Promise<SearchSummary> {
  const response = await apiFetch(`/api/searches/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json()
}

/**
 * Delete a saved search (the server refuses with 409 while it is running, 404 if unknown).
 * Its companies, jobs and people leave the entity pages; applied/connected marks and pins stay.
 */
export async function deleteSearch(id: string): Promise<void> {
  const response = await apiFetch(`/api/searches/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await apiFetch(url, { signal })
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
  const response = await apiFetch(`/api/searches/${encodeURIComponent(searchId)}/people`, {
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
  const response = await apiFetch('/api/statuses', {
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
  const response = await apiFetch('/api/pins', {
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
  shared_background?: string
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

export interface AuthConfig {
  /** False in development: everyone is TEST_USER and there is nothing to sign in to. */
  enabled: boolean
  /** The owner's inbox for access requests; empty if the server doesn't set one. */
  request_email: string
}

export const getAuthConfig = (signal?: AbortSignal) => getJson<AuthConfig>('/api/auth/config', signal)

export type AccessStatus = 'pending' | 'denied'

/** Refused (403) because the owner hasn't approved this email (`pending`) or turned it down. */
export class AccessError extends Error {
  access: AccessStatus

  constructor(message: string, access: AccessStatus) {
    super(message)
    this.access = access
  }
}

async function postAuth(url: string, body: unknown): Promise<Response> {
  const response = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (response.ok) return response
  let detail = `Request failed (${response.status})`
  let access: unknown
  try {
    const parsed = await response.json()
    if (typeof parsed.detail === 'string') detail = parsed.detail
    access = parsed.access
  } catch {
    // Not JSON; keep the generic message.
  }
  if (access === 'pending' || access === 'denied') throw new AccessError(detail, access)
  throw new Error(detail)
}

export async function signIn(email: string, password: string): Promise<User> {
  return (await postAuth('/api/auth/login', { email, password })).json()
}

/** Request access. `'pending'` until the owner approves; the user if pre-approved. */
export async function signUp(email: string, password: string): Promise<User | 'pending'> {
  const response = await postAuth('/api/auth/signup', { email, password })
  return response.status === 202 ? 'pending' : response.json()
}

export async function signOut(): Promise<void> {
  await apiFetch('/api/auth/logout', { method: 'POST' })
}
