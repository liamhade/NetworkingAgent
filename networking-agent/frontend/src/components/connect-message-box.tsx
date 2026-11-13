import { useEffect, useId, useState } from 'react'
import {
  RiArrowDownSLine,
  RiCheckLine,
  RiErrorWarningLine,
  RiFileCopyLine,
  RiLinkedinBoxLine,
} from '@remixicon/react'
import { Button } from '@/components/base/buttons/button'
import { cx } from '@/utils/cx'

interface ConnectMessageBoxProps {
  /** Example LinkedIn connection note; older saved people have none (renders nothing). */
  text?: string
  className?: string
}

type CopyState = 'idle' | 'copied' | 'failed'

const COPY_LABELS: Record<CopyState, string> = {
  idle: 'Copy',
  copied: 'Copied',
  failed: 'Copy failed',
}

const COPY_ICONS = {
  idle: RiFileCopyLine,
  copied: RiCheckLine,
  failed: RiErrorWarningLine,
} as const

/**
 * Expandable blue box with an example LinkedIn connection note for a person, shown below
 * the "Why connect" `AlignmentBox`, with a copy-to-clipboard button.
 */
export function ConnectMessageBox({ text, className }: ConnectMessageBoxProps) {
  const [open, setOpen] = useState(false)
  const [copy, setCopy] = useState<CopyState>('idle')
  const panelId = useId()

  useEffect(() => {
    if (copy === 'idle') return
    const timer = window.setTimeout(() => setCopy('idle'), 2000)
    return () => window.clearTimeout(timer)
  }, [copy])

  if (!text) return null

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopy('copied')
    } catch {
      setCopy('failed')
    }
  }

  return (
    <div
      className={cx(
        'rounded-xl bg-notification-information-background text-notification-information-foreground',
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
        <RiLinkedinBoxLine aria-hidden className="size-3.5 shrink-0" />
        <span className="flex-1">Example LinkedIn message</span>
        <RiArrowDownSLine
          aria-hidden
          className={cx('size-4 shrink-0 transition-transform duration-200', open && 'rotate-180')}
        />
      </button>
      <div id={panelId} hidden={!open} className="flex flex-col gap-1.5 px-2.5 pb-2.5">
        <p className="text-body-2-regular whitespace-pre-line">{text}</p>
        <div className="flex items-center justify-between gap-2">
          <span className="text-caption-1-regular">{text.length} characters</span>
          <Button
            variant="ghost"
            size="xs"
            leadingIcon={COPY_ICONS[copy]}
            onClick={onCopy}
            aria-live="polite"
          >
            {COPY_LABELS[copy]}
          </Button>
        </div>
      </div>
    </div>
  )
}
