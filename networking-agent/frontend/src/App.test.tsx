import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api'
import App from '@/App'
import { BOARDS } from '@/test/boards'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  getCurrentUser: vi.fn(),
  listSearches: vi.fn(),
  listSearchConfigs: vi.fn(),
  getStatuses: vi.fn(),
  getPins: vi.fn(),
  getSearchBoards: vi.fn(),
  getSearchParams: vi.fn(),
  getSavedResume: vi.fn(),
  getSearch: vi.fn(),
  streamSearch: vi.fn(),
  streamSearchEvents: vi.fn(),
  cancelSearch: vi.fn(),
  listEntities: vi.fn(),
}))

const m = vi.mocked(api)

beforeEach(() => {
  m.getCurrentUser.mockResolvedValue({ id: 'TEST_USER', display_name: 'Test', created_at: '' })
  m.listSearches.mockResolvedValue([])
  m.listSearchConfigs.mockResolvedValue([])
  m.getStatuses.mockResolvedValue({ job: {}, person: {} })
  m.getPins.mockResolvedValue({ company: {}, job: {}, person: {} })
  m.getSearchBoards.mockResolvedValue(BOARDS)
  m.getSearchParams.mockResolvedValue(null)
  m.getSavedResume.mockResolvedValue(null)
  m.streamSearch.mockResolvedValue()
  m.streamSearchEvents.mockResolvedValue()
  m.listEntities.mockResolvedValue([])
  window.location.hash = ''
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

describe('App restores the saved search page state', () => {
  it('fills the form and boards from the saved parameters', async () => {
    m.getSearchParams.mockResolvedValue({
      background: 'Saved background',
      location: 'Boston',
      looking_for: 'Saved goal',
      boards: { greenhouse: { enabled: false, max_jobs: 3 } },
    })
    const user = userEvent.setup()
    render(<App />)
    expect(await screen.findByDisplayValue('Saved background')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Boston')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Saved goal')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /search boards/i }))
    expect(screen.getByRole('switch', { name: 'Greenhouse' })).not.toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })).toHaveValue('3')
  })

  it('shows the saved resume as a chip', async () => {
    m.getSavedResume.mockResolvedValue({
      filename: 'cv.pdf',
      size: 2048,
      stored_size: 900,
      uploaded_at: '2026-11-01T15:30:00Z',
      profile: { background: '', location: '', looking_for: '' },
    })
    render(<App />)
    expect(await screen.findByRole('link', { name: 'cv.pdf' })).toBeInTheDocument()
  })

  it('uses empty defaults when nothing is saved', async () => {
    render(<App />)
    await screen.findByText('2 of 3 boards on')
    expect(screen.getByRole('textbox', { name: /your background/i })).toHaveValue('')
    expect(screen.queryByRole('link', { name: /\.pdf$/ })).not.toBeInTheDocument()
  })

  it('does not clobber a reopened past search with late saved params', async () => {
    let resolveParams: (value: api.SearchParams) => void = () => {}
    m.getSearchParams.mockReturnValue(new Promise((resolve) => (resolveParams = resolve)))
    m.listSearches.mockResolvedValue([
      { id: 'a', title: 'Past search', created_at: '2026-11-01T00:00:00Z', status: 'done' },
    ])
    m.getSearch.mockResolvedValue({
      id: 'a',
      title: 'Past search',
      created_at: '2026-11-01T00:00:00Z',
      status: 'done',
      messages: [],
      error: null,
      user_id: 'TEST_USER',
      request: { background: 'Past bg', location: '', looking_for: 'Past goal' },
      results: { summary: 'All done', companies: [] },
    })
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('Past search'))
    await screen.findByText('All done')
    resolveParams({ background: 'Late', location: '', looking_for: 'Late goal' })
    await user.click(screen.getAllByRole('button', { name: /new search/i })[0])
    expect(await screen.findByDisplayValue('Past bg')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Late')).not.toBeInTheDocument()
  })
})

const RUNNING = {
  id: 'run',
  title: 'Climate roles',
  created_at: '2026-11-01T00:00:00Z',
  status: 'running' as const,
}
const REQUEST = { background: 'Bg', location: '', looking_for: 'Climate roles' }

describe('App background searches', () => {
  it('lists a running search and follows it when opened', async () => {
    m.listSearches.mockResolvedValue([RUNNING])
    m.getSearch.mockResolvedValue({
      ...RUNNING,
      user_id: 'TEST_USER',
      request: REQUEST,
      results: { summary: '', companies: [] },
      messages: ['Finding jobs'],
      error: null,
    })
    let finish: () => void = () => {}
    m.streamSearchEvents.mockImplementation(async (_id, onEvent) => {
      onEvent({ type: 'started', search: RUNNING })
      onEvent({ type: 'status', message: 'Finding jobs' })
      await new Promise<void>((resolve) => (finish = resolve))
      onEvent({ type: 'result', data: { summary: 'Found them', companies: [] } })
      onEvent({ type: 'saved', search: { ...RUNNING, status: 'done' } })
    })
    const user = userEvent.setup()
    render(<App />)
    expect(await screen.findByText('Searching…')).toBeInTheDocument()
    await user.click(screen.getByText('Climate roles'))
    expect(await screen.findByText('Finding jobs')).toBeInTheDocument()
    expect(m.streamSearchEvents).toHaveBeenCalledWith('run', expect.any(Function), expect.anything())

    finish()
    expect(await screen.findByText('Found them')).toBeInTheDocument()
    expect(screen.queryByText('Searching…')).not.toBeInTheDocument()
  })

  it('cancels a running search from the panel and marks it cancelled', async () => {
    m.listSearches.mockResolvedValue([RUNNING])
    m.cancelSearch.mockResolvedValue({ ...RUNNING, status: 'cancelled' })
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Cancel search: Climate roles/ }))
    expect(m.cancelSearch).toHaveBeenCalledWith('run')
    expect(await screen.findByText('Cancelled')).toBeInTheDocument()
    expect(screen.queryByText('Searching…')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cancel search/ })).not.toBeInTheDocument()
  })

  it('shows the error and refreshes the list when the cancel is refused', async () => {
    m.listSearches
      .mockResolvedValueOnce([RUNNING])
      .mockResolvedValue([{ ...RUNNING, status: 'done' as const }])
    m.cancelSearch.mockRejectedValue(new Error('That search is not running.'))
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Cancel search/ }))
    expect(await screen.findByText('That search is not running.')).toBeInTheDocument()
    expect(screen.queryByText('Searching…')).not.toBeInTheDocument()
  })

  it('ends a followed search cleanly when it is cancelled', async () => {
    m.listSearches.mockResolvedValue([RUNNING])
    m.getSearch.mockResolvedValue({
      ...RUNNING,
      user_id: 'TEST_USER',
      request: REQUEST,
      results: { summary: '', companies: [] },
      messages: [],
      error: null,
    })
    m.streamSearchEvents.mockImplementation(async (_id, onEvent) => {
      onEvent({ type: 'started', search: RUNNING })
      onEvent({ type: 'cancelled', search: { ...RUNNING, status: 'cancelled' } })
    })
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('Climate roles'))
    expect(await screen.findByText('This search was cancelled.')).toBeInTheDocument()
    expect(screen.getByText('Cancelled')).toBeInTheDocument()
  })

  it('shows why a failed search failed when opened', async () => {
    m.listSearches.mockResolvedValue([{ ...RUNNING, status: 'error' }])
    m.getSearch.mockResolvedValue({
      ...RUNNING,
      status: 'error',
      user_id: 'TEST_USER',
      request: REQUEST,
      results: { summary: '', companies: [] },
      messages: [],
      error: 'This search was interrupted because the server restarted.',
    })
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByText('Climate roles'))
    expect(await screen.findByText(/interrupted because the server restarted/)).toBeInTheDocument()
    expect(m.streamSearchEvents).not.toHaveBeenCalled()
  })

  it('keeps searching while the user visits another page', async () => {
    let signal: AbortSignal | undefined
    let finish: () => void = () => {}
    m.streamSearch.mockImplementation(async (_request, onEvent, abortSignal) => {
      signal = abortSignal
      onEvent({ type: 'started', search: RUNNING })
      await new Promise<void>((resolve) => (finish = resolve))
      onEvent({ type: 'result', data: { summary: 'Done while away', companies: [] } })
      onEvent({ type: 'saved', search: { ...RUNNING, status: 'done' } })
    })
    m.getSearchParams.mockResolvedValue(REQUEST)
    const user = userEvent.setup()
    render(<App />)
    await screen.findByDisplayValue('Climate roles')
    await user.click(screen.getByRole('button', { name: /find opportunities/i }))
    expect(await screen.findByText('Searching…')).toBeInTheDocument() // In the panel at once.

    await user.click(screen.getByRole('link', { name: 'Companies' }))
    expect(signal?.aborted).toBe(false)
    finish()
    await user.click(screen.getByRole('link', { name: 'Search' }))
    expect(await screen.findByText('Done while away')).toBeInTheDocument()
    expect(screen.queryByText('Searching…')).not.toBeInTheDocument()
  })
})
