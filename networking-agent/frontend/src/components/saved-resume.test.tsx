import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/api'
import { Hero } from '@/pages/hero'
import { BOARDS } from '@/test/boards'

vi.mock('@/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api')>()),
  getSearchBoards: vi.fn(),
  getSavedResume: vi.fn(),
  deleteSavedResume: vi.fn(),
}))

const deleteSavedResume = vi.mocked(api.deleteSavedResume)

const saved: api.SavedResume = {
  filename: 'My CV.pdf',
  size: 52_224,
  stored_size: 20_000,
  uploaded_at: '2026-11-01T15:30:00Z',
  profile: { background: 'Analyst', location: 'NYC', looking_for: 'Data roles' },
}
const form: api.SearchRequest = { background: 'Analyst', location: '', looking_for: 'Data' }

beforeEach(() => {
  vi.mocked(api.getSearchBoards).mockResolvedValue(BOARDS)
  deleteSavedResume.mockReset().mockResolvedValue()
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

describe('saved resume chip', () => {
  it('shows the saved file instead of the upload box', () => {
    render(<Hero initial={form} onSubmit={vi.fn()} savedResume={saved} />)
    expect(screen.getByRole('link', { name: 'My CV.pdf' })).toHaveAttribute(
      'href',
      api.savedResumeUrl,
    )
    expect(screen.getByText(/51 KB/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /replace/i })).toBeInTheDocument()
  })

  it('shows the upload box when nothing is saved', () => {
    render(<Hero initial={form} onSubmit={vi.fn()} savedResume={null} />)
    expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'My CV.pdf' })).not.toBeInTheDocument()
  })

  it('removes the saved resume', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Hero initial={form} onSubmit={vi.fn()} savedResume={saved} onSavedResumeChange={onChange} />,
    )
    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(deleteSavedResume).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('keeps the chip and shows an error if removing fails', async () => {
    deleteSavedResume.mockRejectedValue(new Error('nope'))
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Hero initial={form} onSubmit={vi.fn()} savedResume={saved} onSavedResumeChange={onChange} />,
    )
    await user.click(screen.getByRole('button', { name: /remove/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('nope')
    expect(onChange).not.toHaveBeenCalled()
  })

  it('swaps in the upload box to replace, and can go back', async () => {
    const user = userEvent.setup()
    render(<Hero initial={form} onSubmit={vi.fn()} savedResume={saved} />)
    await user.click(screen.getByRole('button', { name: /replace/i }))
    expect(screen.queryByRole('link', { name: 'My CV.pdf' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /keep saved resume/i }))
    expect(screen.getByRole('link', { name: 'My CV.pdf' })).toBeInTheDocument()
  })
})
