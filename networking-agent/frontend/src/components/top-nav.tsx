import {
  RiBriefcaseLine,
  RiBuilding2Line,
  RiSearchLine,
  RiUserLine,
} from '@remixicon/react'
import { cx } from '@/utils/cx'
import { type View, viewHash } from '@/utils/view'

const NAV_ITEMS: { view: View; label: string; icon: typeof RiSearchLine }[] = [
  { view: 'search', label: 'Search', icon: RiSearchLine },
  { view: 'companies', label: 'Companies', icon: RiBuilding2Line },
  { view: 'jobs', label: 'Jobs', icon: RiBriefcaseLine },
  { view: 'people', label: 'People', icon: RiUserLine },
]

interface TopNavProps {
  /** The page being shown; the links change the URL hash and the app follows it. */
  view: View
}

/** Menu bar above the main column: the search view plus the Companies / Jobs / People pages. */
export function TopNav({ view }: TopNavProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-separator-border bg-background-full">
      <nav aria-label="Main" className="mx-auto flex w-full max-w-3xl gap-1 overflow-x-auto px-6 py-2">
        {NAV_ITEMS.map(({ view: target, label, icon: Icon }) => {
          const active = target === view
          return (
            <a
              key={target}
              href={viewHash(target)}
              aria-current={active ? 'page' : undefined}
              className={cx(
                'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-body-medium transition-colors',
                'outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
                active
                  ? 'bg-background-primary-active text-text-primary'
                  : 'text-text-secondary hover:bg-background-primary-hover hover:text-text-primary',
              )}
            >
              <Icon
                aria-hidden
                className={cx(
                  'size-[18px] shrink-0',
                  active ? 'text-foreground-icon-primary' : 'text-foreground-icon-tertiary',
                )}
              />
              {label}
            </a>
          )
        })}
      </nav>
    </header>
  )
}
