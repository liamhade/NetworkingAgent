import { savedResumeUrl, type SavedResume } from '@/api'
import { Icon } from '@/components/icon'
import { formatBytes } from '@/utils/format-bytes'
import { formatRelativeDate } from '@/utils/format-date'

interface SavedResumeChipProps {
  resume: SavedResume
  onReplace: () => void
  onRemove: () => void
  disabled?: boolean
}

/** The resume the user uploaded earlier: name (a download link), size and date, replace / remove. */
export function SavedResumeChip({ resume, onReplace, onRemove, disabled }: SavedResumeChipProps) {
  return (
    <div className="savedres">
      <Icon name="check" />
      <span>
        <a href={savedResumeUrl} download={resume.filename}>
          {resume.filename}
        </a>{' '}
        <span className="meta">
          · {formatBytes(resume.size)} · Saved {formatRelativeDate(new Date(resume.uploaded_at))}
        </span>
      </span>
      <span className="sp" />
      <button type="button" className="btn xs" onClick={onReplace} disabled={disabled}>
        Replace
      </button>
      <button type="button" className="btn xs danger" onClick={onRemove} disabled={disabled}>
        Remove
      </button>
    </div>
  )
}
