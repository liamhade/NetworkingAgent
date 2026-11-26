import { useEffect, useState } from 'react'
import type { User } from '@/api'
import { ChangePasswordDialog } from '@/components/change-password'
import { Icon, type IconName } from '@/components/icon'
import { initials } from '@/utils/initials'
import { useAuth } from '@/utils/auth-context'
import type { Theme } from '@/utils/theme'
import { type View, viewHash } from '@/utils/view'

const NAV_ITEMS: { view: View; label: string; icon: IconName }[] = [
  { view: 'search', label: 'Search', icon: 'search' },
  { view: 'companies', label: 'Companies', icon: 'building' },
  { view: 'jobs', label: 'Jobs', icon: 'briefcase' },
  { view: 'people', label: 'People', icon: 'users' },
]

/** Only for the owner (`user.is_admin`). */
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
          <span className="brand-mark">
            <Icon name="layers" />
          </span>
          <span className="tx">Networking Agent</span>
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
          <div className="user">
            <span className="nm">{name}</span>
            <span className="avatar" aria-hidden="true">
              {initials(name)}
            </span>
            {auth.enabled && (
              <>
                {!auth.localDev && (
                  <button
                    type="button"
                    className="btn xs ghost signout"
                    onClick={() => setChangingPassword(true)}
                  >
                    Change password
                  </button>
                )}
                <button type="button" className="btn xs ghost signout" onClick={auth.signOut}>
                  Sign out
                </button>
              </>
            )}
          </div>
        )}
      </header>
      <div className="shell">
        {sidebar}
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
