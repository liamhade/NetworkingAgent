import { render, screen, within } from '@testing-library/react'
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
  createSearchConfig: vi.fn(),
  updateSearchConfig: vi.fn(),
  deleteSearchConfig: vi.fn(),
  getStatuses: vi.fn(),
  getPins: vi.fn(),
  getSearchBoards: vi.fn(),
  getSearchParams: vi.fn(),
  getSavedResume: vi.fn(),
  getSearch: vi.fn(),
}))

const m = vi.mocked(api)

const config = (
  id: string,
  name: string,
  params: Partial<api.SearchParams> = {},
): api.SearchConfig => ({
  id,
  name,
  params: { background: `${name} bg`, location: 'Boston', looking_for: `${name} goal`, ...params },
  created_at: '2026-11-01T12:00:00Z',
  updated_at: '2026-11-01T12:00:00Z',
})

beforeEach(() => {
  vi.resetAllMocks()
  m.getCurrentUser.mockResolvedValue({ id: 'TEST_USER', display_name: 'Test', created_at: '' })
  m.listSearches.mockResolvedValue([])
  m.listSearchConfigs.mockResolvedValue([])
  m.getStatuses.mockResolvedValue({ job: {}, person: {} })
  m.getPins.mockResolvedValue({ company: {}, job: {}, person: {} })
  m.getSearchBoards.mockResolvedValue(BOARDS)
  m.getSearchParams.mockResolvedValue(null)
  m.getSavedResume.mockResolvedValue(null)
  window.location.hash = ''
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

describe('search configurations panel', () => {
  it('lists the saved configurations in order', async () => {
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech'), config('b', 'Climate')])
    render(<App />)
    const panel = await screen.findByRole('complementary', { name: 'Search configurations' })
    const items = await within(panel).findAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent('Fintech')
    expect(items[1]).toHaveTextContent('Climate')
  })

  it('shows an empty hint when none are saved', async () => {
    render(<App />)
    expect(await screen.findByText(/save the form as a configuration/i)).toBeInTheDocument()
  })

  it('saves the current form including the boards, then lets you name it', async () => {
    m.createSearchConfig.mockImplementation(async (params) => ({
      ...config('new', 'Search Configuration #1'),
      params,
    }))
    m.updateSearchConfig.mockImplementation(async (id, changes) => config(id, changes.name ?? ''))
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('2 of 3 boards on')
    await user.type(screen.getByRole('textbox', { name: /your background/i }), 'My background')
    await user.type(screen.getByRole('textbox', { name: /looking for/i }), 'Goal')
    await user.click(screen.getByRole('button', { name: /search boards/i }))
    await user.click(screen.getByRole('switch', { name: 'Built In NYC' }))

    await user.click(screen.getByRole('button', { name: /save current configuration/i }))
    expect(m.createSearchConfig).toHaveBeenCalledTimes(1)
    const [saved, name] = m.createSearchConfig.mock.calls[0]
    expect(name).toBeUndefined()
    expect(saved).toMatchObject({ background: 'My background', looking_for: 'Goal' })
    expect(saved.boards?.builtin_nyc.enabled).toBe(false)
    expect(saved.boards?.greenhouse.enabled).toBe(true)

    // The new row opens for naming, starting from the server's default name.
    const field = await screen.findByRole('textbox', { name: 'Configuration name' })
    expect(field).toHaveValue('Search Configuration #1')
    await user.clear(field)
    await user.type(field, '  Fintech roles {Enter}')
    expect(m.updateSearchConfig).toHaveBeenCalledWith('new', { name: 'Fintech roles' })
    expect(await screen.findByRole('button', { name: 'Load Fintech roles' })).toBeInTheDocument()
  })

  it('renames inline: empty names are refused and Escape cancels', async () => {
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech')])
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Rename Fintech' }))
    const field = screen.getByRole('textbox', { name: 'Configuration name' })
    await user.clear(field)
    await user.keyboard('{Enter}')
    expect(screen.getByText('Give it a name.')).toBeInTheDocument()
    expect(m.updateSearchConfig).not.toHaveBeenCalled()
    await user.type(field, 'Other{Escape}')
    expect(screen.queryByRole('textbox', { name: 'Configuration name' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Load Fintech' })).toBeInTheDocument()
    expect(m.updateSearchConfig).not.toHaveBeenCalled()
  })

  it('shows the server error when a rename fails and keeps editing', async () => {
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech')])
    m.updateSearchConfig.mockRejectedValue(new Error('Name must be at most 80 characters.'))
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Rename Fintech' }))
    await user.type(screen.getByRole('textbox', { name: 'Configuration name' }), 'x{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('at most 80')
    expect(screen.getByRole('textbox', { name: 'Configuration name' })).toBeInTheDocument()
  })

  it('loads a configuration into the form, boards included', async () => {
    m.listSearchConfigs.mockResolvedValue([
      config('a', 'Fintech', { boards: { greenhouse: { enabled: false, max_jobs: 3 } } }),
    ])
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Load Fintech' }))
    expect(await screen.findByDisplayValue('Fintech bg')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Boston')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Fintech goal')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: /search boards/i }))
    expect(screen.getByRole('switch', { name: 'Greenhouse' })).not.toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })).toHaveValue('3')
    expect(screen.getByRole('button', { name: 'Load Fintech' })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('overwrites a configuration with the current form', async () => {
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech')])
    m.updateSearchConfig.mockResolvedValue(config('a', 'Fintech', { background: 'Edited' }))
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Load Fintech' }))
    const background = await screen.findByRole('textbox', { name: /your background/i })
    await user.clear(background)
    await user.type(background, 'Edited')
    await user.click(screen.getByRole('button', { name: 'Overwrite Fintech with the current form' }))
    expect(m.updateSearchConfig).toHaveBeenCalledWith('a', {
      params: expect.objectContaining({ background: 'Edited', location: 'Boston' }),
    })
  })

  it('deletes after confirming; keeping cancels', async () => {
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech'), config('b', 'Climate')])
    m.deleteSearchConfig.mockResolvedValue()
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Delete Fintech' }))
    await user.click(screen.getByRole('button', { name: 'Keep' }))
    expect(m.deleteSearchConfig).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Delete Fintech' }))
    await user.click(screen.getByRole('button', { name: 'Confirm delete Fintech' }))
    expect(m.deleteSearchConfig).toHaveBeenCalledWith('a')
    expect(screen.queryByRole('button', { name: 'Load Fintech' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Load Climate' })).toBeInTheDocument()
  })

  it('does not clobber a loaded configuration with late saved params', async () => {
    let resolveParams: (value: api.SearchParams) => void = () => {}
    m.getSearchParams.mockReturnValue(new Promise((resolve) => (resolveParams = resolve)))
    m.listSearchConfigs.mockResolvedValue([config('a', 'Fintech')])
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Load Fintech' }))
    resolveParams({ background: 'Late', location: '', looking_for: 'Late goal' })
    expect(await screen.findByDisplayValue('Fintech bg')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Late')).not.toBeInTheDocument()
  })
})
