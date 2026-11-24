import { useEffect, useRef, useState } from 'react'
import { Icon } from '@/components/icon'
import { StatusToggle } from '@/components/status-toggle'
import { useToast } from '@/utils/use-toast'
import { cx } from '@/utils/cx'
import { initials } from '@/utils/initials'

/** LinkedIn's limit for a connection note. */
const MESSAGE_LIMIT = 300

export interface DrawerPerson {
  name: string
  title: string
  company: string
  profileUrl: string
  /** Why this person is worth contacting. */
  alignment: string
  /** The example LinkedIn note from the backend; older searches have none. */
  message?: string
  /** Entity key for the CONNECTED mark (empty: not keyed, no toggle). */
  key: string
}

interface ConnectDrawerProps {
  /** The person to message; null closes the drawer. */
  person: DrawerPerson | null
  connected: boolean
  onToggleConnected: (connected: boolean) => void
  onClose: () => void
}

/**
 * Side drawer for messaging one person: why connect, the example LinkedIn note (editable,
 * with a 300-character counter), Copy, Open LinkedIn and Mark connected. Modal: focus is
 * trapped inside and Escape closes it.
 */
export function ConnectDrawer({ person, connected, onToggleConnected, onClose }: ConnectDrawerProps) {
  const toast = useToast()
  const panel = useRef<HTMLElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const returnFocus = useRef<Element | null>(null)
  // Edits and the "Copied!" state belong to one person; opening another starts fresh.
  const [draft, setDraft] = useState<{ person: DrawerPerson | null; text: string }>({
    person: null,
    text: '',
  })
  const [copiedFor, setCopiedFor] = useState<DrawerPerson | null>(null)
  const text = draft.person === person ? draft.text : (person?.message ?? '')
  const copied = person !== null && copiedFor === person
  const open = person !== null

  useEffect(() => {
    if (!open) return
    returnFocus.current = document.activeElement
    closeButton.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previousOverflow
      const target = returnFocus.current
      if (target instanceof HTMLElement && target.isConnected) target.focus()
    }
  }, [open])

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopiedFor(null), 2000)
    return () => window.clearTimeout(timer)
  }, [copied])

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') return onClose()
    if (event.key !== 'Tab' || !panel.current) return
    const focusable = panel.current.querySelectorAll<HTMLElement>(
      'button:not(:disabled),a[href],select,textarea',
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedFor(person)
      toast('Message copied to clipboard')
    } catch {
      toast('Could not copy. Select the text and copy it instead.')
    }
  }

  const length = text.length
  return (
    <>
      <div className={cx('drawer-scrim', open && 'open')} aria-hidden="true" onClick={onClose} />
      <aside
        ref={panel}
        className={cx('drawer', open && 'open')}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        aria-hidden={!open}
        onKeyDown={onKeyDown}
      >
        {person && (
          <>
            <header>
              <span className="pavatar" aria-hidden="true">
                {initials(person.name)}
              </span>
              <div className="who">
                <h2 id="drawer-title">Message {person.name}</h2>
                <p>{[person.title, person.company].filter(Boolean).join(' at ')}</p>
              </div>
              <button
                ref={closeButton}
                type="button"
                className="ibtn"
                aria-label="Close message panel"
                onClick={onClose}
              >
                <Icon name="x" size="lg" />
              </button>
            </header>
            <div className="dbody">
              {person.alignment && (
                <div className="note p">
                  <div className="lab">Why connect</div>
                  {person.alignment}
                </div>
              )}
              {person.message ? (
                <div className="field msgbox">
                  <label htmlFor="drawer-msg">Example LinkedIn message</label>
                  <textarea
                    id="drawer-msg"
                    value={text}
                    onChange={(event) => setDraft({ person, text: event.target.value })}
                  />
                  <div className="cc">
                    <span>Edit freely before sending.</span>
                    <span className="num">
                      <span className={cx(length > MESSAGE_LIMIT && 'over')}>
                        {length} / {MESSAGE_LIMIT}
                      </span>{' '}
                      characters
                    </span>
                  </div>
                </div>
              ) : (
                <p className="empty-msg">
                  This search has no example message for {person.name}. Run the search again to
                  get one.
                </p>
              )}
            </div>
            <div className="dfoot">
              {person.message && (
                <button type="button" className="btn pri" id="dcopy" onClick={copy}>
                  <Icon name={copied ? 'check' : 'copy'} />
                  <span>{copied ? 'Copied!' : 'Copy message'}</span>
                </button>
              )}
              {person.profileUrl && (
                <a className="btn" href={person.profileUrl} target="_blank" rel="noreferrer">
                  <Icon name="ext" />
                  Open LinkedIn
                </a>
              )}
              {person.key && (
                <StatusToggle
                  kind="person"
                  name={person.name}
                  isSelected={connected}
                  offLabel="Mark as connected"
                  onChange={onToggleConnected}
                />
              )}
            </div>
          </>
        )}
      </aside>
    </>
  )
}
