import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import {
  deleteSavedResume,
  getSavedResume,
  parseResume,
  type BoardsConfig,
  type SavedResume,
  type SearchRequest,
} from '@/api'
import { Icon } from '@/components/icon'
import { SavedResumeChip } from '@/components/saved-resume'
import { SearchBoards } from '@/components/search-boards'
import { anyBoardOn } from '@/utils/boards'
import { formatSchools, parseSchools } from '@/utils/schools'
import { cx } from '@/utils/cx'

const MAX_RESUME_BYTES = 10 * 1024 * 1024

interface HeroProps {
  initial: SearchRequest
  onSubmit: (request: SearchRequest) => void
  /** The resume saved earlier (null: none); shown as a file chip instead of the upload box. */
  savedResume?: SavedResume | null
  onSavedResumeChange?: (resume: SavedResume | null) => void
  /** Called with the form as it would be searched (boards filled in) whenever it changes. */
  onChange?: (request: SearchRequest) => void
  /** The right rail's "Saved searches" card. */
  configs?: React.ReactNode
}

type ResumeState =
  | { status: 'idle' }
  | { status: 'reading'; name: string }
  | { status: 'done'; name: string }
  | { status: 'error'; message: string }

/** The search page: the form card, with saved configurations and a short how-to on the right. */
export function Hero({
  initial,
  onSubmit,
  savedResume = null,
  onSavedResumeChange,
  onChange,
  configs,
}: HeroProps) {
  const [form, setForm] = useState<SearchRequest>(initial)
  const [resume, setResume] = useState<ResumeState>({ status: 'idle' })
  // The boards config as the panel shows it (defaults filled in); null until the list loads.
  const [shownBoards, setShownBoards] = useState<BoardsConfig | null>(null)
  // True while the user picks a new file to replace the saved resume.
  const [replacing, setReplacing] = useState(false)

  // The schools box is free text; keep what was typed and sync only when the form changes
  // from elsewhere (a resume fills it in, a saved search is restored).
  const [schoolsText, setSchoolsText] = useState(formatSchools(initial.education))
  useEffect(() => {
    setSchoolsText((shown) =>
      formatSchools(parseSchools(shown)) === formatSchools(form.education)
        ? shown
        : formatSchools(form.education),
    )
  }, [form.education])

  const update = (field: 'background' | 'location' | 'looking_for') => (value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  const handleResume = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      return setResume({ status: 'error', message: 'Please choose a PDF file.' })
    }
    if (file.size > MAX_RESUME_BYTES) {
      return setResume({ status: 'error', message: 'That PDF is over 10 MB.' })
    }
    setResume({ status: 'reading', name: file.name })
    try {
      const profile = await parseResume(file)
      setForm((current) => ({
        ...current,
        background: profile.background || current.background,
        location: profile.location || current.location,
        looking_for: profile.looking_for || current.looking_for,
        education: profile.education?.length ? profile.education : current.education,
      }))
      setResume({ status: 'done', name: file.name })
      setReplacing(false)
      // The server saved it; fetch the metadata for the chip. Best effort.
      getSavedResume()
        .then((saved) => onSavedResumeChange?.(saved))
        .catch(console.error)
    } catch (error) {
      setResume({ status: 'error', message: (error as Error).message })
    }
  }

  const removeResume = async () => {
    try {
      await deleteSavedResume()
      onSavedResumeChange?.(null)
      setResume({ status: 'idle' })
    } catch (error) {
      setResume({ status: 'error', message: (error as Error).message })
    }
  }

  const boardsOk = shownBoards === null || anyBoardOn(shownBoards)
  const missing = !form.background.trim()
    ? 'Add your background to continue.'
    : !form.looking_for.trim()
      ? 'Tell us what you are looking for to continue.'
      : !boardsOk
        ? 'Turn on at least one search board to continue.'
        : null
  const canSubmit = missing === null && resume.status !== 'reading'

  // The form as a search would send it: boards as shown (defaults filled in), so a search
  // (or a saved configuration) is self-describing. The resume file is not part of it.
  const current: SearchRequest = shownBoards ? { ...form, boards: shownBoards } : form
  useEffect(() => {
    onChange?.(current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, shownBoards])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit(current)
  }

  return (
    <div className="wrap">
      <div className="head search-head">
        <div>
          <h1>Find the people behind the job</h1>
          <div className="sub">
            Tell the agent what you want. It returns companies, the jobs open there, and the people
            to message first.
          </div>
        </div>
      </div>

      <div className="sgrid">
        <form className="card form" onSubmit={submit} noValidate>
          <div>
            <h2>
              Start from your resume <span className="pill neu">Optional</span>
            </h2>
            <p className="lead">Upload a PDF and we fill in your background for you.</p>
            {savedResume && !replacing ? (
              <SavedResumeChip
                resume={savedResume}
                onReplace={() => setReplacing(true)}
                onRemove={removeResume}
                disabled={resume.status === 'reading'}
              />
            ) : (
              <>
                <DropZone onFile={handleResume} disabled={resume.status === 'reading'} />
                {replacing && (
                  <button
                    type="button"
                    className="btn xs ghost"
                    onClick={() => setReplacing(false)}
                    disabled={resume.status === 'reading'}
                  >
                    Keep saved resume
                  </button>
                )}
              </>
            )}
            <ResumeStatus state={resume} />
          </div>

          <Field
            label="Your background"
            required
            hint="Role, skills and the projects you are proudest of."
          >
            {(id, describedBy) => (
              <textarea
                id={id}
                rows={4}
                required
                aria-describedby={describedBy}
                placeholder="I'm a data analyst with 3 years of SQL and Python experience in payments…"
                value={form.background}
                onChange={(event) => update('background')(event.target.value)}
              />
            )}
          </Field>
          <Field
            label="School(s)"
            hint="Optional. We also look for people at each company who went to your school."
          >
            {(id, describedBy) => (
              <input
                id={id}
                type="text"
                aria-describedby={describedBy}
                placeholder="Cornell University"
                value={schoolsText}
                onChange={(event) => {
                  setSchoolsText(event.target.value)
                  setForm((current) => ({
                    ...current,
                    education: parseSchools(event.target.value),
                  }))
                }}
              />
            )}
          </Field>
          <Field label="Location">
            {(id) => (
              <input
                id={id}
                type="text"
                placeholder="Brooklyn, NY"
                value={form.location}
                onChange={(event) => update('location')(event.target.value)}
              />
            )}
          </Field>
          <Field label="What you are looking for" required>
            {(id) => (
              <textarea
                id={id}
                rows={3}
                required
                placeholder="Senior analytics roles at fintech startups, hybrid or remote"
                value={form.looking_for}
                onChange={(event) => update('looking_for')(event.target.value)}
              />
            )}
          </Field>

          <SearchBoards
            value={form.boards}
            onChange={(boards) => setForm((existing) => ({ ...existing, boards }))}
            onLoaded={setShownBoards}
          />

          <div className="submit">
            <button className="btn pri" type="submit" disabled={!canSubmit}>
              <Icon name="search" />
              Find opportunities
            </button>
            <span className={cx('why', missing && 'bad')} aria-live="polite">
              {missing ?? 'Takes a few minutes. You can leave this page while it runs.'}
            </span>
          </div>
        </form>

        <aside className="rail" aria-label="Saved searches and help">
          {configs}
          <section className="card" aria-labelledby="howh">
            <h2 id="howh">How results are organised</h2>
            <ol className="how">
              <li>
                <span className="ic tint-co">
                  <Icon name="building" />
                </span>
                <div>
                  <b>Companies first</b>
                  <span>Ranked by fit. Open one to see everything there.</span>
                </div>
              </li>
              <li>
                <span className="ic tint-job">
                  <Icon name="briefcase" />
                </span>
                <div>
                  <b>Jobs beside people</b>
                  <span>Each opening sits next to the people who can help.</span>
                </div>
              </li>
              <li>
                <span className="ic tint-per">
                  <Icon name="users" />
                </span>
                <div>
                  <b>Messages ready</b>
                  <span>Pick a person, read why they matter, copy the note.</span>
                </div>
              </li>
            </ol>
          </section>
        </aside>
      </div>
    </div>
  )
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string
  required?: boolean
  hint?: string
  children: (id: string, describedBy?: string) => React.ReactNode
}) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>
        {label}
        {required && (
          <>
            {' '}
            <span className="req" aria-hidden="true">
              *
            </span>
            <span className="sr">(required)</span>
          </>
        )}
      </label>
      {children(id, hint ? `${id}-hint` : undefined)}
      {hint && (
        <div className="hint" id={`${id}-hint`}>
          {hint}
        </div>
      )}
    </div>
  )
}

/** Click or drop a PDF. */
function DropZone({ onFile, disabled }: { onFile: (file: File) => void; disabled: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  return (
    <div
      className={cx('drop', drag && 'drag')}
      onDragOver={(event) => {
        event.preventDefault()
        setDrag(true)
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDrag(false)
        const file = event.dataTransfer.files[0]
        if (file && !disabled) onFile(file)
      }}
    >
      <span className="ic">
        <Icon name="upload" size="lg" />
      </span>
      <div className="grow">
        <b>Drop a PDF here</b>
        <p>or choose a file, up to 10 MB</p>
      </div>
      <button
        type="button"
        className="btn sm"
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        Choose file
      </button>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        aria-label="Resume PDF"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onFile(file)
          event.target.value = ''
        }}
      />
    </div>
  )
}

function ResumeStatus({ state }: { state: ResumeState }) {
  if (state.status === 'idle') return null
  if (state.status === 'reading') {
    return (
      <p className="resume-msg">
        <span className="spin" aria-hidden="true" />
        Reading {state.name}…
      </p>
    )
  }
  if (state.status === 'done') {
    return (
      <p className="resume-msg">
        <Icon name="check" size="sm" />
        Filled in from {state.name}. Review and edit below.
      </p>
    )
  }
  return (
    <p role="alert" className="resume-msg err">
      <Icon name="alert" size="sm" />
      {state.message}
    </p>
  )
}
