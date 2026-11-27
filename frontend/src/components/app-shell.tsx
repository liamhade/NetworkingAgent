import { useEffect, useRef, useState } from 'react'
import type { User } from '@/api'
import { BrandMark } from '@/components/brand-mark'
import { ChangePasswordDialog } from '@/components/change-password'
import { PanelResizer } from '@/components/panel-resizer'
import { Icon, type IconName } from '@/components/icon'
import { initials } from '@/utils/initials'
import { useAuth } from '@/utils/auth-context'
import { SIDEBAR_SPEC, useSidebarWidth } from '@/utils/sidebar-width'
import type { Theme } from '@/utils/theme'
import { type View, viewHash } from '@/utils/view'

const NAV_ITEMS: { view: View; label: string; icon: IconName }[] = [
  { view: 'search', label: 'Search', icon: 'search' },
  { view: 'companies', label: 'Companies', icon: 'building' },
  { view: 'jobs', label: 'Jobs', icon: 'briefcase' },
  { view: 'people', label: 'People', icon: 'users' },
  { view: 'about', label: 'About', icon: 'info' },
]

/** Only for the owner (`user.is_admin`); after About. */
const ADMIN_ITEM: (typeof NAV_ITEMS)[number] = { view: 'admin', label: 'Admin', icon: 'shield' }

interface AppShellProps {
  view: View
  user: User | null
  theme: Theme
  onThemeChange: (theme: Theme) => void
  /** The Previous Searches sidebar. */
  sidebar: React.ReactNode
  /** Below 980px the sidebar is a drawer opened from the menu button. */
  sidebarOpen: boolean
  onSidebarOpenChange: (open: boolean) => void
  children: React.ReactNode
}

/**
 * Top bar (brand, Search / Companies / Jobs / People [/ Admin for the owner], theme toggle,
 * user) and the page grid.
 */
export function AppShell({
  view,
  user,
  theme,
  onThemeChange,
  sidebar,
  sidebarOpen,
  onSidebarOpenChange,
  children,
}: AppShellProps) {
  useEffect(() => {
    if (!sidebarOpen) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onSidebarOpenChange(false)
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [sidebarOpen, onSidebarOpenChange])

  const name = user?.display_name || user?.id || ''
  const auth = useAuth()
  const [changingPassword, setChangingPassword] = useState(false)
  const navItems = user?.is_admin ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS
  const sidebarWidth = useSidebarWidth()
  return (
    <>
      <header className="topbar">
        <a className="skip" href="#main">
          Skip to content
        </a>
        <button
          type="button"
          className="ibtn menu-btn"
          aria-label="Open previous searches"
          aria-controls="side"
          aria-expanded={sidebarOpen}
          onClick={() => onSidebarOpenChange(!sidebarOpen)}
        >
          <Icon name="menu" size="lg" />
        </button>
        <a className="brand" href={viewHash('search')}>
          <BrandMark />
          <span className="tx">enishi</span>
        </a>
        <nav className="nav" aria-label="Primary">
          {navItems.map((item) => (
            <a
              key={item.view}
              href={viewHash(item.view)}
              aria-current={item.view === view ? 'page' : undefined}
              aria-label={item.label}
            >
              <Icon name={item.icon} />
              <span className="lbl">{item.label}</span>
            </a>
          ))}
        </nav>
        <span className="sp" />
        <div className="theme-tog" role="group" aria-label="Colour theme">
          {(['light', 'dark'] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={theme === option}
              aria-label={option === 'light' ? 'Light theme' : 'Dark theme'}
              title={option === 'light' ? 'Light' : 'Dark'}
              onClick={() => onThemeChange(option)}
            >
              <Icon name={option === 'light' ? 'sun' : 'moon'} />
            </button>
          ))}
        </div>
        {name && (
          <UserMenu
            name={name}
            onChangePassword={
              auth.enabled && !auth.localDev ? () => setChangingPassword(true) : undefined
            }
            onSignOut={auth.enabled ? auth.signOut : undefined}
          />
        )}
      </header>
      <div className="shell" style={{ '--side-w': `${sidebarWidth.width}px` } as React.CSSProperties}>
        {sidebar}
        <PanelResizer
          {...sidebarWidth}
          spec={SIDEBAR_SPEC}
          label="Resize previous searches"
          controls="side"
          className="side-resize"
        />
        <main className="main" id="main">
          {children}
        </main>
      </div>
      {changingPassword && <ChangePasswordDialog onClose={() => setChangingPassword(false)} />}
      <div
        className={sidebarOpen ? 'scrim open' : 'scrim'}
        aria-hidden="true"
        onClick={() => onSidebarOpenChange(false)}
      />
    </>
  )
}

/**
 * The avatar and name in the top bar. When accounts are on, clicking them opens a menu with
 * Change password (not in LOCAL_DEV_MODE) and Sign out.
 */
function UserMenu({
  name,
  onChangePassword,
  onSignOut,
}: {
  name: string
  onChangePassword?: () => void
  onSignOut?: () => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) =>
      root.current?.contains(event.target as Node) || setOpen(false)
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      root.current?.querySelector<HTMLButtonElement>('.user-btn')?.focus()
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const identity = (
    <>
      <span className="nm">{name}</span>
      <span className="avatar" aria-hidden="true">
        {initials(name)}
      </span>
    </>
  )
  if (!onChangePassword && !onSignOut) return <div className="user">{identity}</div>

  const choose = (action: () => void) => () => {
    setOpen(false)
    action()
  }
  return (
    <div className="user" ref={root}>
      <button
        type="button"
        className="user-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="user-menu"
        aria-label={`Account menu: ${name}`}
        onClick={() => setOpen((current) => !current)}
      >
        {identity}
        <Icon name="chevron" size="sm" />
      </button>
      {open && (
        <div className="user-menu" id="user-menu" role="menu" aria-label="Account">
          {onChangePassword && (
            <button type="button" role="menuitem" onClick={choose(onChangePassword)}>
              Change password
            </button>
          )}
          {onSignOut && (
            <button type="button" role="menuitem" onClick={choose(onSignOut)}>
              Sign out
            </button>
          )}
        </div>
      )}
    </div>
  )
}
