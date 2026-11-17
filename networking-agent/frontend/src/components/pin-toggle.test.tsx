import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PinToggle } from '@/components/pin-toggle'

describe('PinToggle', () => {
  it('is a button named "Pin <name>"', () => {
    render(<PinToggle name="Acme" isPinned={false} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Pin Acme' })).toBeInTheDocument()
  })

  it('falls back to "Pin for later" without a name', () => {
    render(<PinToggle name="" isPinned={false} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Pin for later' })).toBeInTheDocument()
  })

  it('unpinned: aria-pressed false, with a decorative pin icon', () => {
    const { container } = render(<PinToggle name="Acme" isPinned={false} onChange={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Pin Acme' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(button).toHaveClass('ibtn', 'pin')
    expect(button).toHaveAttribute('title', 'Pin for later')
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })

  it('pinned: aria-pressed true (the theme fills the icon) and an Unpin tooltip', () => {
    render(<PinToggle name="Acme" isPinned onChange={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Pin Acme' })
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(button).toHaveAttribute('title', 'Unpin')
  })

  it('clicking calls onChange with the next state', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = render(<PinToggle name="Acme" isPinned={false} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Pin Acme' }))
    expect(onChange).toHaveBeenLastCalledWith(true)

    rerender(<PinToggle name="Acme" isPinned onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Pin Acme' }))
    expect(onChange).toHaveBeenLastCalledWith(false)
    expect(onChange).toHaveBeenCalledTimes(2)
  })

  it('is controlled: the pressed state follows isPinned, not the click', async () => {
    const user = userEvent.setup()
    render(<PinToggle name="Acme" isPinned={false} onChange={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Pin Acme' })
    await user.click(button)
    expect(button).toHaveAttribute('aria-pressed', 'false')
  })

  it('toggles from the keyboard', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<PinToggle name="Acme" isPinned={false} onChange={onChange} />)
    await user.tab()
    expect(screen.getByRole('button', { name: 'Pin Acme' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(onChange).toHaveBeenCalledWith(true)
  })
})
