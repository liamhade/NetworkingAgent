import { useState, type FormEvent } from 'react'
import { RiCheckLine, RiErrorWarningLine, RiSearchLine } from '@remixicon/react'
import { parseResume, type SearchRequest } from '@/api'
import { Button } from '@/components/base/buttons/button'
import { FileUpload } from '@/components/base/file-upload/file-upload'
import { Input } from '@/components/base/input/input'
import { Spinner } from '@/components/base/spinner/spinner'
import { Textarea } from '@/components/base/textarea/textarea'

interface HeroProps {
  initial: SearchRequest
  onSubmit: (request: SearchRequest) => void
}

type ResumeState =
  | { status: 'idle' }
  | { status: 'reading'; name: string }
  | { status: 'done'; name: string }
  | { status: 'error'; message: string }

export function Hero({ initial, onSubmit }: HeroProps) {
  const [form, setForm] = useState<SearchRequest>(initial)
  const [resume, setResume] = useState<ResumeState>({ status: 'idle' })

  const update = (field: keyof SearchRequest) => (value: string) =>
    setForm((current) => ({ ...current, [field]: value }))

  const handleResume = async (file: File) => {
    setResume({ status: 'reading', name: file.name })
    try {
      const profile = await parseResume(file)
      setForm((current) => ({
        background: profile.background || current.background,
        location: profile.location || current.location,
        looking_for: profile.looking_for || current.looking_for,
      }))
      setResume({ status: 'done', name: file.name })
    } catch (error) {
      setResume({ status: 'error', message: (error as Error).message })
    }
  }

  const canSubmit =
    form.background.trim() !== '' && form.looking_for.trim() !== '' && resume.status !== 'reading'

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (canSubmit) onSubmit(form)
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-16">
      <header className="flex flex-col gap-3 text-center">
        <h1 className="text-display-3-semibold text-text-primary">
          Find your next role, and the people behind it
        </h1>
        <p className="text-body-regular text-text-secondary">
          Tell us about yourself. We'll find companies worth researching, open jobs that fit, and
          people to reach out to.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-headline-medium text-text-primary">Start from your resume</h2>
          <span className="text-caption-1-medium text-text-tertiary">Optional · PDF</span>
        </div>
        <FileUpload
          allowedExtensions={['pdf']}
          maxBytes={10 * 1024 * 1024}
          onUploadComplete={handleResume}
        />
        <ResumeStatus state={resume} />
      </section>

      <form onSubmit={submit} className="flex flex-col gap-5">
        <Textarea
          label="Your background"
          placeholder="I'm a data analyst with 3 years of SQL and Python experience in payments…"
          value={form.background}
          onChange={update('background')}
          rows={5}
          resize="vertical"
          isRequired
        />
        <Input
          label="Where you live"
          placeholder="Brooklyn, NY"
          value={form.location}
          onChange={update('location')}
        />
        <Textarea
          label="What you're looking for"
          placeholder="Senior analytics roles at fintech startups, hybrid or remote"
          value={form.looking_for}
          onChange={update('looking_for')}
          rows={3}
          resize="vertical"
          isRequired
        />
        <Button type="submit" variant="primary" leadingIcon={RiSearchLine} disabled={!canSubmit}>
          Find opportunities
        </Button>
      </form>
    </main>
  )
}

function ResumeStatus({ state }: { state: ResumeState }) {
  if (state.status === 'idle') return null
  if (state.status === 'reading') {
    return (
      <p className="flex items-center gap-2 text-body-2-regular text-text-secondary">
        <Spinner size="sm" aria-hidden />
        Reading {state.name}…
      </p>
    )
  }
  if (state.status === 'done') {
    return (
      <p className="flex items-center gap-2 text-body-2-regular text-text-secondary">
        <RiCheckLine aria-hidden className="size-4 text-foreground-icon-primary" />
        Filled in from {state.name}. Review and edit below.
      </p>
    )
  }
  return (
    <p role="alert" className="flex items-center gap-2 text-body-2-regular text-text-error-primary">
      <RiErrorWarningLine aria-hidden className="size-4" />
      {state.message}
    </p>
  )
}
