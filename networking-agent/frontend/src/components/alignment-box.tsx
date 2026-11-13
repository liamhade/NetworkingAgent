import { useId, useState } from 'react'
import { RiArrowDownSLine, RiSparkling2Line } from '@remixicon/react'
import { cx } from '@/utils/cx'

interface AlignmentBoxProps {
  text: string
  label?: string
  className?: string
}

/** Expandable green box explaining how the user aligns with a company, job or person. */
export function AlignmentBox({ text, label = 'How you align', className }: AlignmentBoxProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  if (!text) return null

  return (
    <div
      className={cx(
        'rounded-xl bg-notification-success-background text-state-success-text',
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className={cx(
          'flex w-full items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-start text-caption-1-semibold',
          'outline-none focus-visible:ring-2 focus-visible:ring-border-focus-ring',
        )}
      >
        <RiSparkling2Line aria-hidden className="size-3.5 shrink-0" />
        <span className="flex-1">{label}</span>
        <RiArrowDownSLine
          aria-hidden
          className={cx('size-4 shrink-0 transition-transform duration-200', open && 'rotate-180')}
        />
      </button>
      <div id={panelId} hidden={!open} className="px-2.5 pb-2.5 text-body-2-regular">
        {text}
      </div>
    </div>
  )
}
