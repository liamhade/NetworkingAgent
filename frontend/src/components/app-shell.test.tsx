import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from '@/components/app-shell'
import { AuthContext } from '@/utils/auth-context'
import { SIDEBAR_DEFAULT, SIDEBAR_MAX, SIDEBAR_WIDTH_KEY } from '@/utils/sidebar-width'

function renderShell() {
  return render(
    <AppShell
      view="search"
      user={null}
      theme="light"
      onThemeChange={() => {}}
      sidebar={<aside id="side" />}
      sidebarOpen={false}
      onSidebarOpenChange={() => {}}
    >
      <p>app</p>
    </AppShell>,
  )
}

const handle = () => screen.getByRole('separator', { name: 'Resize previous searches' })
const shellWidth = (container: HTMLElement) =>
  (container.querySelector('.shell') as HTMLElement).style.getPropertyValue('--side-w')

afterEach(() => localStorage.removeItem(SIDEBAR_WIDTH_KEY))

describe('sidebar resize', () => {
  it('nudges with the arrow keys, saves the width, and resets on double-click', () => {
    const { container } = renderShell()
    expect(shellWidth(container)).toBe(`${SIDEBAR_DEFAULT}px`)

    fireEvent.keyDown(handle(), { key: 'ArrowRight' })
    expect(handle().getAttribute('aria-valuenow')).toBe(String(SIDEBAR_DEFAULT + 16))
    expect(localStorage.getItem(SIDEBAR_WIDTH_KEY)).toBe(String(SIDEBAR_DEFAULT + 16))

    fireEvent.keyDown(handle(), { key: 'End' })
    expect(shellWidth(container)).toBe(`${SIDEBAR_MAX}px`)

    fireEvent.doubleClick(handle())
    expect(shellWidth(container)).toBe(`${SIDEBAR_DEFAULT}px`)
  })

  it('restores the saved width, clamped to the limits', () => {
    localStorage.setItem(SIDEBAR_WIDTH_KEY, '9999')
    const { container } = renderShell()
    expect(shellWidth(container)).toBe(`${SIDEBAR_MAX}px`)
  })
})

describe('account menu', () => {
  it('opens from the avatar with Change password and Sign out, and closes on Escape', async () => {
    const signOut = vi.fn(async () => {})
    const user = userEvent.setup()
    render(
      <AuthContext.Provider value={{ enabled: true, localDev: false, signOut }}>
        <AppShell
          view="search"
          user={{ id: 'u1', display_name: 'a@x.com', created_at: '2026-11-24T00:00:00Z' }}
          theme="light"
          onThemeChange={() => {}}
          sidebar={null}
          sidebarOpen={false}
          onSidebarOpenChange={() => {}}
        >
          <p>app</p>
        </AppShell>
      </AuthContext.Provider>,
    )
    expect(screen.queryByRole('menu')).toBeNull()
    const button = screen.getByRole('button', { name: 'Account menu: a@x.com' })
    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('menuitem', { name: 'Change password' })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).toBeNull()

    await user.click(button)
    await user.click(screen.getByRole('menuitem', { name: 'Sign out' }))
    expect(signOut).toHaveBeenCalled()
    expect(screen.queryByRole('menu')).toBeNull()
  })
})
