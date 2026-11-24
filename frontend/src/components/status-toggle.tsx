import { Icon } from '@/components/icon'

/** Visible labels: [off, on]. */
const LABELS = {
  job: ['Mark applied', 'Applied'],
  person: ['Mark connected', 'Connected'],
} as const

interface StatusToggleProps {
  kind: keyof typeof LABELS
  /** The job title or person's name, for the accessible name ("Mark applied: Data Analyst"). */
  name: string
  isSelected: boolean
  onChange: (isSelected: boolean) => void
  /** Overrides the "off" label (the message drawer says "Mark as connected"). */
  offLabel?: string
}

/**
 * APPLIED / CONNECTED toggle on job and person rows: a dashed pill that reads "Mark applied"
 * when off, and a solid teal "Applied" with a check when on (`aria-pressed`).
 */
export function StatusToggle({ kind, name, isSelected, onChange, offLabel }: StatusToggleProps) {
  const [off, on] = LABELS[kind]
  return (
    <button
      type="button"
      className={`status ${kind === 'job' ? 'app' : 'con'}`}
      aria-pressed={isSelected}
      aria-label={name ? `${off}: ${name}` : off}
      onClick={() => onChange(!isSelected)}
    >
      {isSelected && <Icon name="check" />}
      <span className="on">{on}</span>
      <span className="off">{offLabel ?? off}</span>
    </button>
  )
}
