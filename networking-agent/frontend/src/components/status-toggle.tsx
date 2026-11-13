import { RiCheckLine } from '@remixicon/react'
import { ToggleButton } from 'react-aria-components'
import { CHIP_COLORS } from '@/components/base/badges/chip'
import { cx } from '@/utils/cx'

/** Toggle labels, exactly as shown to the user. */
const STATUS_LABELS = {
  job: { on: 'APPLIED', off: 'NOT APPLIED' },
  person: { on: 'CONNECTED', off: 'NOT CONNECTED' },
} as const

interface StatusToggleProps {
  kind: keyof typeof STATUS_LABELS
  isSelected: boolean
  onChange: (isSelected: boolean) => void
}

/**
 * APPLIED / CONNECTED toggle on job and person rows. A React Aria `ToggleButton` styled
 * like the BoardUI caption `Chip`: lime with a check when on, neutral when off. The
 * visible text is the accessible name; React Aria adds `aria-pressed` for the state.
 */
export function StatusToggle({ kind, isSelected, onChange }: StatusToggleProps) {
  const labels = STATUS_LABELS[kind]
  return (
    <ToggleButton
      isSelected={isSelected}
      onChange={onChange}
      className={cx(
        'inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 whitespace-nowrap text-caption-1-semibold select-none',
        'button-press-motion outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
        isSelected ? CHIP_COLORS.lime : CHIP_COLORS.neutral,
        !isSelected && 'hover:bg-background-tertiary-hover',
      )}
    >
      {isSelected && <RiCheckLine aria-hidden className="size-3.5 shrink-0" />}
      {isSelected ? labels.on : labels.off}
    </ToggleButton>
  )
}
