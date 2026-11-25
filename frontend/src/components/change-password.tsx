import { useEffect, useId, useRef, useState } from 'react'
import { changePassword } from '@/api'

const MIN_PASSWORD = 8

/**
 * Change your own password (current + new + repeat). A modal: Escape or the backdrop closes it.
 * After an owner reset, this is how a user swaps the temporary password for their own.
 */
export function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const ids = { title: useId(), current: useId(), next: useId(), repeat: useId(), hint: useId() }
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const first = useRef<HTMLInputElement>(null)

  useEffect(() => {
    first.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const mismatch = repeat.length > 0 && repeat !== next
  const canSubmit =
    !busy && current.length > 0 && next.length >= MIN_PASSWORD && repeat === next

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      await changePassword(current, next)
      setDone(true)
    } catch (caught) {
      setError((caught as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-scrim" onClick={onClose}>
      <form
        className="card auth-card modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={ids.title}
        onClick={(event) => event.stopPropagation()}
        onSubmit={submit}
        noValidate
      >
        <h2 id={ids.title}>Change password</h2>
        {done ? (
          <>
            <p className="hint" role="status">
              Your password is changed. Use the new one next time you sign in.
            </p>
            <button type="button" className="btn pri auth-submit" onClick={onClose}>
              Done
            </button>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor={ids.current}>Current password</label>
              <input
                ref={first}
                id={ids.current}
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor={ids.next}>New password</label>
              <input
                id={ids.next}
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                aria-describedby={ids.hint}
                required
              />
              <div className="hint" id={ids.hint}>
                At least {MIN_PASSWORD} characters.
              </div>
            </div>
            <div className="field">
              <label htmlFor={ids.repeat}>Repeat new password</label>
              <input
                id={ids.repeat}
                type="password"
                autoComplete="new-password"
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                aria-invalid={mismatch || undefined}
                required
              />
              {mismatch && <div className="hint err">The passwords don&rsquo;t match.</div>}
            </div>
            {error && (
              <div className="alert" role="alert">
                {error}
              </div>
            )}
            <div className="modal-acts">
              <button type="button" className="btn" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn pri" disabled={!canSubmit}>
                {busy ? 'Saving…' : 'Change password'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
