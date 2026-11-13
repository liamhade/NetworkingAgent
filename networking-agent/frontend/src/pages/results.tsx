import {
  RiArrowLeftLine,
  RiBuilding2Line,
  RiBriefcaseLine,
  RiErrorWarningLine,
  RiExternalLinkLine,
  RiUserLine,
} from '@remixicon/react'
import type {
  CompanyResult,
  JobResult,
  PersonResult,
  SearchResults,
  StatusKind,
  StatusMap,
} from '@/api'
import { AlignmentBox } from '@/components/alignment-box'
import { ConnectMessageBox } from '@/components/connect-message-box'
import { AgentThinking } from '@/components/application/agent-thinking/agent-thinking'
import { Chip } from '@/components/base/badges/chip'
import { Button } from '@/components/base/buttons/button'
import { StatusToggle } from '@/components/status-toggle'

type ToggleStatus = (kind: StatusKind, key: string, active: boolean) => void

interface ResultsProps {
  statuses: string[]
  results: SearchResults | null
  error: string | null
  running: boolean
  /** APPLIED / CONNECTED marks for the current user, by entity key. */
  entityStatuses: StatusMap
  statusError: string | null
  onToggleStatus: ToggleStatus
  onBack: () => void
}

export function Results({
  statuses,
  results,
  error,
  running,
  entityStatuses,
  statusError,
  onToggleStatus,
  onBack,
}: ResultsProps) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <div>
        <Button variant="ghost" size="small" leadingIcon={RiArrowLeftLine} onClick={onBack}>
          New search
        </Button>
      </div>

      {running && <Progress statuses={statuses} />}

      {error && <ErrorBanner message={error} />}
      {statusError && <ErrorBanner message={statusError} />}

      {results && (
        <>
          <header className="flex flex-col gap-2">
            <h1 className="text-title-1-semibold text-text-primary">Your opportunities</h1>
            <p className="text-body-regular text-text-secondary">{results.summary}</p>
          </header>
          {results.companies.length === 0 ? (
            <p className="text-body-regular text-text-secondary">
              No matching companies found. Try broadening what you're looking for.
            </p>
          ) : (
            <ol className="flex flex-col gap-4">
              {results.companies.map((company, index) => (
                <li key={`${company.name}-${index}`}>
                  <CompanyCard
                    company={company}
                    rank={index + 1}
                    entityStatuses={entityStatuses}
                    onToggleStatus={onToggleStatus}
                  />
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </main>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-2xl border border-border-error-default p-4 text-body-regular text-text-error-primary"
    >
      <RiErrorWarningLine aria-hidden className="mt-0.5 size-5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

function Progress({ statuses }: { statuses: string[] }) {
  return (
    <section
      aria-live="polite"
      className="flex flex-col gap-3 rounded-3xl border border-border-button-default p-5"
    >
      <AgentThinking variant="wave" label={statuses.at(-1) ?? 'Starting'} showTimer />
      <p className="text-caption-1-medium text-text-tertiary">
        Searching job boards and LinkedIn can take a few minutes.
      </p>
      {statuses.length > 1 && (
        <ul className="flex flex-col gap-1 text-body-2-regular text-text-tertiary">
          {statuses.slice(0, -1).map((status, index) => (
            <li key={index}>{status}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  if (!href) return <span>{children}</span>
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded-sm outline-none hover:underline focus-visible:ring-2 focus-visible:ring-border-focus-ring"
    >
      {children}
      <RiExternalLinkLine aria-hidden className="size-3.5 shrink-0 text-foreground-icon-tertiary" />
    </a>
  )
}

interface CompanyCardProps {
  company: CompanyResult
  rank: number
  entityStatuses: StatusMap
  onToggleStatus: ToggleStatus
}

function CompanyCard({ company, rank, entityStatuses, onToggleStatus }: CompanyCardProps) {
  return (
    <article className="flex flex-col gap-4 rounded-3xl border border-border-button-default bg-background-primary-default p-5">
      <div className="flex flex-col gap-2">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-background-secondary-default text-foreground-icon-secondary">
            <RiBuilding2Line aria-hidden className="size-5" />
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <h2 className="text-title-3-semibold text-text-primary">
              <span className="text-text-tertiary">{rank}. </span>
              <ExternalLink href={company.url}>{company.name}</ExternalLink>
            </h2>
            <p className="text-body-2-regular text-text-secondary">{company.description}</p>
          </div>
          <div className="flex shrink-0 gap-1">
            <Chip variant="caption" color="soft">
              {company.jobs.length} {company.jobs.length === 1 ? 'job' : 'jobs'}
            </Chip>
            <Chip variant="caption" color="soft">
              {company.people.length} {company.people.length === 1 ? 'contact' : 'contacts'}
            </Chip>
          </div>
        </div>
        <AlignmentBox text={company.alignment} />
      </div>

      {company.jobs.length > 0 && (
        <Section icon={RiBriefcaseLine} title="Job openings">
          {company.jobs.map((job, index) => (
            <JobRow
              key={`${job.key || job.url}-${index}`}
              job={job}
              applied={entityStatuses.job[job.key] ?? false}
              onToggle={(active) => onToggleStatus('job', job.key, active)}
            />
          ))}
        </Section>
      )}

      {company.people.length > 0 && (
        <Section icon={RiUserLine} title="People to connect with">
          {company.people.map((person, index) => (
            <PersonRow
              key={`${person.key || person.profile_url}-${index}`}
              person={person}
              connected={entityStatuses.person[person.key] ?? false}
              onToggle={(active) => onToggleStatus('person', person.key, active)}
            />
          ))}
        </Section>
      )}
    </article>
  )
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof RiUserLine
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-2 border-t border-separator-border pt-4">
      <h3 className="flex items-center gap-1.5 text-caption-1-semibold text-text-tertiary uppercase">
        <Icon aria-hidden className="size-4" />
        {title}
      </h3>
      <ul className="flex flex-col gap-3">{children}</ul>
    </section>
  )
}

interface RowToggleProps {
  onToggle: (active: boolean) => void
}

function JobRow({ job, applied, onToggle }: { job: JobResult; applied: boolean } & RowToggleProps) {
  const meta = [job.location, job.salary].filter(Boolean).join(' · ')
  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="text-body-medium text-text-primary">
            <ExternalLink href={job.url}>{job.title}</ExternalLink>
          </span>
          {meta && <span className="text-body-2-regular text-text-tertiary">{meta}</span>}
        </div>
        {job.key && <StatusToggle kind="job" isSelected={applied} onChange={onToggle} />}
      </div>
      <AlignmentBox text={job.alignment} />
    </li>
  )
}

function PersonRow({
  person,
  connected,
  onToggle,
}: { person: PersonResult; connected: boolean } & RowToggleProps) {
  return (
    <li className="flex flex-col gap-1.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="text-body-medium text-text-primary">
            <ExternalLink href={person.profile_url}>{person.name}</ExternalLink>
          </span>
          {person.title && (
            <span className="text-body-2-regular text-text-tertiary">{person.title}</span>
          )}
        </div>
        {person.key && <StatusToggle kind="person" isSelected={connected} onChange={onToggle} />}
      </div>
      <AlignmentBox text={person.alignment} label="Why connect" />
      <ConnectMessageBox text={person.connect_message} />
    </li>
  )
}
