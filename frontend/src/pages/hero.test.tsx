import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api'
import { Hero } from '@/pages/hero'
import { BOARDS } from '@/test/boards'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  getSearchBoards: vi.fn(),
}))

const getSearchBoards = vi.mocked(api.getSearchBoards)

beforeEach(() => {
  getSearchBoards.mockResolvedValue(BOARDS)
  // jsdom has no ResizeObserver (the resume upload box measures itself with one).
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

const filled: api.SearchRequest = {
  background: 'Data analyst',
  location: 'NYC',
  looking_for: 'Analytics roles',
}

describe('Hero search boards', () => {
  it('sends the default boards config with the search', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<Hero initial={filled} onSubmit={onSubmit} />)
    await screen.findByText('2 of 3 boards on')
    await user.click(screen.getByRole('button', { name: /find opportunities/i }))
    expect(onSubmit).toHaveBeenCalledWith({
      ...filled,
      boards: {
        builtin_nyc: { enabled: true, max_jobs: 45 },
        greenhouse: { enabled: true, max_jobs: 8 },
        usajobs: { enabled: false, max_jobs: 20 },
      },
    })
  })

  it('sends the edited boards config', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<Hero initial={filled} onSubmit={onSubmit} />)
    await user.click(await screen.findByRole('button', { name: /search boards/i }))
    await user.click(screen.getByRole('switch', { name: 'Built In NYC' }))
    const field = screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })
    await user.clear(field)
    await user.type(field, '12')
    await user.tab()
    await user.click(screen.getByRole('button', { name: /find opportunities/i }))
    expect(onSubmit).toHaveBeenCalledWith({
      ...filled,
      boards: {
        builtin_nyc: { enabled: false, max_jobs: 45 },
        greenhouse: { enabled: true, max_jobs: 12 },
        usajobs: { enabled: false, max_jobs: 20 },
      },
    })
  })

  it('shows the boards of a reopened search', async () => {
    const user = userEvent.setup()
    const initial = {
      ...filled,
      boards: { greenhouse: { enabled: false, max_jobs: 3 } },
    }
    render(<Hero initial={initial} onSubmit={vi.fn()} />)
    await user.click(await screen.findByRole('button', { name: /search boards/i }))
    expect(screen.getByRole('switch', { name: 'Greenhouse' })).not.toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Jobs from Greenhouse' })).toHaveValue('3')
  })

  it('blocks the search while every board is off', async () => {
    const user = userEvent.setup()
    render(<Hero initial={filled} onSubmit={vi.fn()} />)
    await user.click(await screen.findByRole('button', { name: /search boards/i }))
    await user.click(screen.getByRole('switch', { name: 'Built In NYC' }))
    await user.click(screen.getByRole('switch', { name: 'Greenhouse' }))
    expect(screen.getByRole('button', { name: /find opportunities/i })).toBeDisabled()
  })

  it('still searches if the board list fails to load', async () => {
    getSearchBoards.mockRejectedValue(new Error('down'))
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<Hero initial={filled} onSubmit={onSubmit} />)
    await screen.findByText('Could not load the board list')
    await user.click(screen.getByRole('button', { name: /find opportunities/i }))
    expect(onSubmit).toHaveBeenCalledWith(filled)
  })
})
