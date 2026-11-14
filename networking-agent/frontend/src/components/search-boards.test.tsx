import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api'
import { SearchBoards } from '@/components/search-boards'
import { anyBoardOn, resolveBoards } from '@/utils/boards'
import { BOARDS } from '@/test/boards'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  getSearchBoards: vi.fn(),
}))

const getSearchBoards = vi.mocked(api.getSearchBoards)

beforeEach(() => {
  getSearchBoards.mockResolvedValue(BOARDS)
})

async function open() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: /search boards/i }))
  return user
}

describe('resolveBoards', () => {
  it('fills defaults, clamps limits and never turns on an unavailable board', () => {
    const config = resolveBoards(BOARDS, {
      builtin_nyc: { enabled: false, max_jobs: 5000 },
      usajobs: { enabled: true, max_jobs: 0 },
    })
    expect(config.builtin_nyc).toEqual({ enabled: false, max_jobs: 100 })
    expect(config.greenhouse).toEqual({ enabled: true, max_jobs: 8 })
    expect(config.usajobs).toEqual({ enabled: false, max_jobs: 1 })
    expect(anyBoardOn(config)).toBe(true)
    expect(anyBoardOn(resolveBoards([BOARDS[2]]))).toBe(false)
  })
})

describe('SearchBoards', () => {
  it('is collapsed and summarises how many boards are on', async () => {
    render(<SearchBoards onChange={vi.fn()} />)
    const trigger = await screen.findByRole('button', {
      name: /search boards/i,
    })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(await screen.findByText('2 of 3 boards on')).toBeInTheDocument()
    expect(screen.queryByRole('switch', { name: 'Built In NYC' })).not.toBeInTheDocument()
  })

  it('renders every board from the API list with labeled switches and number inputs', async () => {
    render(<SearchBoards onChange={vi.fn()} />)
    await open()
    for (const board of BOARDS) {
      expect(screen.getByRole('switch', { name: board.label })).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: `Jobs from ${board.label}` })).toBeInTheDocument()
    }
    expect(screen.getByRole('switch', { name: 'Built In NYC' })).toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Jobs from Built In NYC' })).toHaveValue('45')
    expect(screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })).toHaveValue('8')
  })

  it('shows an unavailable board off and disabled, with the reason', async () => {
    render(<SearchBoards onChange={vi.fn()} />)
    await open()
    const usajobs = screen.getByRole('switch', { name: 'USAJOBS' })
    expect(usajobs).toBeDisabled()
    expect(usajobs).not.toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Jobs from USAJOBS' })).toBeDisabled()
    expect(screen.getByText(/needs an api key/i)).toBeInTheDocument()
  })

  it('toggling a board reports the full config with that board off', async () => {
    const onChange = vi.fn()
    render(<SearchBoards onChange={onChange} />)
    const user = await open()
    await user.click(screen.getByRole('switch', { name: 'Greenhouse' }))
    expect(onChange).toHaveBeenLastCalledWith({
      builtin_nyc: { enabled: true, max_jobs: 45 },
      greenhouse: { enabled: false, max_jobs: 8 },
      usajobs: { enabled: false, max_jobs: 20 },
    })
  })

  it('disables the number input of a board that is off', async () => {
    render(
      <SearchBoards value={{ greenhouse: { enabled: false, max_jobs: 8 } }} onChange={vi.fn()} />,
    )
    await open()
    expect(screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })).toBeDisabled()
    expect(screen.getByRole('switch', { name: 'Greenhouse' })).not.toBeChecked()
  })

  it('reports a typed limit, clamped to the board limits', async () => {
    const onChange = vi.fn()
    render(<SearchBoards onChange={onChange} />)
    const user = await open()
    const field = screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })
    await user.clear(field)
    await user.type(field, '500')
    await user.tab()
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ greenhouse: { enabled: true, max_jobs: 40 } }),
    )
  })

  it('disables the increase stepper at the maximum', async () => {
    render(
      <SearchBoards value={{ greenhouse: { enabled: true, max_jobs: 40 } }} onChange={vi.fn()} />,
    )
    await open()
    const field = screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })
    const increase = field.closest('[role=group]')?.querySelector('[slot=increment]')
    expect(increase).toBeDisabled()
  })

  it('warns when every board is off', async () => {
    render(
      <SearchBoards
        value={{
          builtin_nyc: { enabled: false, max_jobs: 45 },
          greenhouse: { enabled: false, max_jobs: 8 },
        }}
        onChange={vi.fn()}
      />,
    )
    await open()
    expect(screen.getByRole('alert')).toHaveTextContent(/at least one board/i)
  })

  it('reports the resolved config once loaded', async () => {
    const onLoaded = vi.fn()
    render(<SearchBoards onChange={vi.fn()} onLoaded={onLoaded} />)
    await waitFor(() =>
      expect(onLoaded).toHaveBeenLastCalledWith({
        builtin_nyc: { enabled: true, max_jobs: 45 },
        greenhouse: { enabled: true, max_jobs: 8 },
        usajobs: { enabled: false, max_jobs: 20 },
      }),
    )
  })

  it('explains a failed board list', async () => {
    getSearchBoards.mockRejectedValue(new Error('Request failed (500)'))
    render(<SearchBoards onChange={vi.fn()} />)
    await open()
    expect(await screen.findByRole('alert')).toHaveTextContent(/request failed \(500\)/i)
  })
})
