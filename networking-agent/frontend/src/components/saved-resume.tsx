import { RiCloseLine, RiFileTextLine, RiRefreshLine } from '@remixicon/react'
import { savedResumeUrl, type SavedResume } from '@/api'
import { Button } from '@/components/base/buttons/button'
import { formatBytes } from '@/utils/format-bytes'
import { formatRelativeDate } from '@/utils/format-date'

interface SavedResumeChipProps {
  resume: SavedResume
  onReplace: () => void
  onRemove: () => void
  disabled?: boolean
}

/** The resume the user uploaded earlier: name, size and date, with replace / remove. */
export function SavedResumeChip({ resume, onReplace, onRemove, disabled }: SavedResumeChipProps) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border-button-default bg-background-primary-default px-3 py-2.5">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-background-secondary-default text-foreground-icon-secondary">
        <RiFileTextLine aria-hidden className="size-5" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <a
          href={savedResumeUrl}
          download={resume.filename}
          className="truncate text-body-1-medium text-text-primary hover:underline"
        >
          {resume.filename}
        </a>
        <span className="text-caption-1-medium text-text-tertiary">
          {formatBytes(resume.size)} · Saved {formatRelativeDate(new Date(resume.uploaded_at))}
        </span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="small"
        leadingIcon={RiRefreshLine}
        onClick={onReplace}
        disabled={disabled}
      >
        Replace
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="small"
        leadingIcon={RiCloseLine}
        onClick={onRemove}
        disabled={disabled}
      >
        Remove
      </Button>
    </div>
  )
}
