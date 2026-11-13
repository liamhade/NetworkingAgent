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

  it('unpinned: aria-pressed false and the outline icon', () => {
    const { container } = render(<PinToggle name="Acme" isPinned={false} onChange={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Pin Acme' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(button).toHaveClass('text-foreground-icon-tertiary')
    expect(button).not.toHaveClass('text-button-ghost-foreground')
    const icon = container.querySelector('svg')
    expect(icon).toHaveAttribute('aria-hidden')
  })

  it('pinned: aria-pressed true, accent styling and a different (filled) icon', () => {
    const unpinned = render(<PinToggle name="Acme" isPinned={false} onChange={vi.fn()} />)
    const outlinePath = unpinned.container.querySelector('svg path')?.getAttribute('d')
    unpinned.unmount()

    const { container } = render(<PinToggle name="Acme" isPinned onChange={vi.fn()} />)
    const button = screen.getByRole('button', { name: 'Pin Acme' })
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(button).toHaveClass('text-button-ghost-foreground')
    const filledPath = container.querySelector('svg path')?.getAttribute('d')
    expect(filledPath).toBeTruthy()
    expect(filledPath).not.toBe(outlinePath)
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
