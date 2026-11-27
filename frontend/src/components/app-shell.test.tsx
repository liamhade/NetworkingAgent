import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { AppShell } from '@/components/app-shell'
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
