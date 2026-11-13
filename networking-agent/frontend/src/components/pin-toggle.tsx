import { RiPushpinFill, RiPushpinLine } from '@remixicon/react'
import { ToggleButton } from 'react-aria-components'
import { cx } from '@/utils/cx'

interface PinToggleProps {
  /** What is being pinned, for the accessible name ("Pin Acme"). */
  name: string
  isPinned: boolean
  onChange: (isPinned: boolean) => void
}

/**
 * Icon-only "pin for later" toggle on company, job and person cards. A React Aria
 * `ToggleButton` (so it exposes `aria-pressed`) using the ghost-button accent tokens when
 * pinned and a quiet tertiary icon otherwise.
 */
export function PinToggle({ name, isPinned, onChange }: PinToggleProps) {
  const Icon = isPinned ? RiPushpinFill : RiPushpinLine
  return (
    <ToggleButton
      isSelected={isPinned}
      onChange={onChange}
      aria-label={`Pin ${name || 'for later'}`}
      className={cx(
        'inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md select-none',
        'button-press-motion outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
        isPinned
          ? 'bg-button-ghost-background text-button-ghost-foreground hover:bg-button-ghost-hover'
          : 'text-foreground-icon-tertiary hover:bg-background-secondary-hover hover:text-foreground-icon-secondary',
      )}
    >
      <Icon aria-hidden className="size-4" />
    </ToggleButton>
  )
}
