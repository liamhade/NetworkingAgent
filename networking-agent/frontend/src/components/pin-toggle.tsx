import { Icon } from '@/components/icon'

interface PinToggleProps {
  /** What is being pinned, for the accessible name ("Pin Acme"). */
  name: string
  isPinned: boolean
  onChange: (isPinned: boolean) => void
}

/** Icon-only "pin for later" toggle (`aria-pressed`); filled terracotta when pinned. */
export function PinToggle({ name, isPinned, onChange }: PinToggleProps) {
  return (
    <button
      type="button"
      className="ibtn pin"
      aria-pressed={isPinned}
      aria-label={`Pin ${name || 'for later'}`}
      title={isPinned ? 'Unpin' : 'Pin for later'}
      onClick={() => onChange(!isPinned)}
    >
      <Icon name="pin" />
    </button>
  )
}
