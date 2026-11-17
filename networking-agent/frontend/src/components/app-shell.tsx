import { useEffect } from 'react'
import type { User } from '@/api'
import { Icon, type IconName } from '@/components/icon'
import { initials } from '@/utils/initials'
import type { Theme } from '@/utils/theme'
import { type View, viewHash } from '@/utils/view'

const NAV_ITEMS: { view: View; label: string; icon: IconName }[] = [
  { view: 'search', label: 'Search', icon: 'search' },
  { view: 'companies', label: 'Companies', icon: 'building' },
  { view: 'jobs', label: 'Jobs', icon: 'briefcase' },
  { view: 'people', label: 'People', icon: 'users' },
]

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

/** Top bar (brand, Search / Companies / Jobs / People, theme toggle, user) and the page grid. */
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
          {NAV_ITEMS.map((item) => (
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
          </div>
        )}
      </header>
      <div className="shell">
        {sidebar}
        <main className="main" id="main">
          {children}
        </main>
      </div>
      <div
        className={sidebarOpen ? 'scrim open' : 'scrim'}
        aria-hidden="true"
        onClick={() => onSidebarOpenChange(false)}
      />
    </>
  )
}
