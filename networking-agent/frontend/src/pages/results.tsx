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
  PinKind,
  PinMap,
  SearchResults,
  StatusKind,
  StatusMap,
} from '@/api'
import { AlignmentBox } from '@/components/alignment-box'
import { ConnectMessageBox } from '@/components/connect-message-box'
import { FindPeopleButton } from '@/components/find-people-button'
import { AgentThinking } from '@/components/application/agent-thinking/agent-thinking'
import { Chip } from '@/components/base/badges/chip'
import { Button } from '@/components/base/buttons/button'
import { PinToggle } from '@/components/pin-toggle'
import { StatusToggle } from '@/components/status-toggle'

type ToggleStatus = (kind: StatusKind, key: string, active: boolean) => void
type TogglePin = (kind: PinKind, key: string, pinned: boolean) => void
/** A company came back from an on-demand people search; replace it in the results. */
type CompanyFound = (company: CompanyResult) => void

interface ResultsProps {
  statuses: string[]
  results: SearchResults | null
  error: string | null
  running: boolean
  /** APPLIED / CONNECTED marks for the current user, by entity key. */
  entityStatuses: StatusMap
  statusError: string | null
  onToggleStatus: ToggleStatus
  /** Pinned companies / jobs / people for the current user, by entity key. */
  pins: PinMap
  pinError: string | null
  onTogglePin: TogglePin
  /** Id of the saved search shown; on-demand people searches need it. Null until saved. */
  searchId: string | null
  onCompanyFound: CompanyFound
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
  pins,
  pinError,
  onTogglePin,
  searchId,
  onCompanyFound,
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
      {pinError && <ErrorBanner message={pinError} />}

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
                    pins={pins}
                    onTogglePin={onTogglePin}
                    searchId={searchId}
                    onCompanyFound={onCompanyFound}
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
  pins: PinMap
  onTogglePin: TogglePin
  searchId: string | null
  onCompanyFound: CompanyFound
}

function CompanyCard({
  company,
  rank,
  entityStatuses,
  onToggleStatus,
  pins,
  onTogglePin,
  searchId,
  onCompanyFound,
}: CompanyCardProps) {
  const companyKey = company.key
  const searchedEmpty = company.people_searched && company.people.length === 0
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
          <div className="flex shrink-0 items-center gap-1">
            {company.score != null && (
              <Chip variant="caption" color="soft">
                Fit {company.score}
              </Chip>
            )}
            <Chip variant="caption" color="soft">
              {company.jobs.length} {company.jobs.length === 1 ? 'job' : 'jobs'}
            </Chip>
            <Chip variant="caption" color="soft">
              {company.people.length} {company.people.length === 1 ? 'contact' : 'contacts'}
            </Chip>
            {companyKey && (
              <PinToggle
                name={company.name}
                isPinned={pins.company[companyKey] ?? false}
                onChange={(pinned) => onTogglePin('company', companyKey, pinned)}
              />
            )}
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
              pinned={pins.job[job.key] ?? false}
              onTogglePin={(pinned) => onTogglePin('job', job.key, pinned)}
              findPeople={
                companyKey && job.key ? (
                  <FindPeopleButton
                    searchId={searchId}
                    companyKey={companyKey}
                    jobKey={job.key}
                    target={`${job.title} at ${company.name}`}
                    onFound={onCompanyFound}
                  />
                ) : null
              }
            />
          ))}
        </Section>
      )}

      {searchedEmpty && (
        <Section icon={RiUserLine} title="People to connect with">
          <li className="text-body-2-regular text-text-tertiary">
            No current employees found yet.
          </li>
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
              pinned={pins.person[person.key] ?? false}
              onTogglePin={(pinned) => onTogglePin('person', person.key, pinned)}
            />
          ))}
        </Section>
      )}

      {companyKey && (
        <FindPeopleButton
          searchId={searchId}
          companyKey={companyKey}
          target={company.name}
          label={company.people.length > 0 ? 'Find more people' : undefined}
          onFound={onCompanyFound}
        />
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
  pinned: boolean
  onTogglePin: (pinned: boolean) => void
}

function JobRow({
  job,
  applied,
  onToggle,
  pinned,
  onTogglePin,
  findPeople,
}: { job: JobResult; applied: boolean; findPeople: React.ReactNode } & RowToggleProps) {
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
        {job.key && (
          <div className="flex shrink-0 items-center gap-1">
            <StatusToggle kind="job" isSelected={applied} onChange={onToggle} />
            <PinToggle name={job.title} isPinned={pinned} onChange={onTogglePin} />
          </div>
        )}
      </div>
      <AlignmentBox text={job.alignment} />
      {findPeople}
    </li>
  )
}

function PersonRow({
  person,
  connected,
  onToggle,
  pinned,
  onTogglePin,
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
        {person.key && (
          <div className="flex shrink-0 items-center gap-1">
            <StatusToggle kind="person" isSelected={connected} onChange={onToggle} />
            <PinToggle name={person.name} isPinned={pinned} onChange={onTogglePin} />
          </div>
        )}
      </div>
      <AlignmentBox text={person.alignment} label="Why connect" />
      <ConnectMessageBox text={person.connect_message} />
    </li>
  )
}
