import { useState } from 'react'
import { Icon } from '@/components/icon'
import { PinToggle } from '@/components/pin-toggle'
import { StatusToggle } from '@/components/status-toggle'
import { cx } from '@/utils/cx'
import type { JobEntry } from '@/utils/job-list'
import { companyTooltip } from './company-tooltip'
import { Contacts } from './contacts'
import { FitMeter } from './fit-meter'
import type { RowContext } from './row-context'

/** One ranked job: rank, title, company tag, facts, fit, reason and the contacts at the company. */
export function JobCard({
  entry,
  otherJobs,
  ctx,
}: {
  entry: JobEntry
  /** Other jobs of the same company in the list. */
  otherJobs: number
  ctx: RowContext
}) {
  const { job, company, companyId, position, id } = entry
  const [alignOpen, setAlignOpen] = useState(false)
  const pinned = !!job.key && !!ctx.pins.job[job.key]
  const applied = !!job.key && !!ctx.statuses.job[job.key]
  return (
    <article className={cx('jcard', pinned && 'pinned', applied && 'done')} id={id}>
      <div className="jrank num" aria-label={`Rank ${position}`}>
        #{position}
      </div>
      <div className="jmain">
        <div className="rtop">
          <div className="rmain">
            {job.url ? (
              <a className="rtitle" href={job.url} target="_blank" rel="noreferrer">
                {job.title}
                <Icon name="ext" />
                <span className="sr"> (opens job posting)</span>
              </a>
            ) : (
              <span className="rtitle plain">{job.title}</span>
            )}
            <div className="rmeta">
              <button
                type="button"
                className="cotag"
                aria-pressed={ctx.selectedCompanies.has(companyId)}
                title={companyTooltip(company)}
                onClick={() => ctx.toggleCompany(companyId)}
              >
                <Icon name="building" />
                {company.name}
              </button>
              {job.location && (
                <span>
                  <Icon name="pin2" size="sm" />
                  {job.location}
                </span>
              )}
              {job.salary && <span className="sal">{job.salary}</span>}
              {job.years_required && (
                <span className="yrs">
                  <Icon name="clock" size="sm" />
                  {job.years_required}
                </span>
              )}
            </div>
          </div>
          <FitMeter score={job.score} />
        </div>
        {job.reason && <p className="jreason">{job.reason}</p>}
        <div className="ract">
          {job.key && (
            <StatusToggle
              kind="job"
              name={job.title}
              isSelected={applied}
              onChange={(value) => ctx.onToggleStatus('job', job.key, value)}
            />
          )}
          {job.key && (
            <PinToggle
              name={job.title}
              isPinned={pinned}
              onChange={(value) => ctx.pin('job', job.key, job.title, value)}
            />
          )}
          {job.url && (
            <a className="btn xs" href={job.url} target="_blank" rel="noreferrer">
              Open posting
              <Icon name="ext" size="sm" />
              <span className="sr"> (opens in a new tab)</span>
            </a>
          )}
          {job.alignment && (
            <button
              type="button"
              className="disc"
              aria-expanded={alignOpen}
              onClick={() => setAlignOpen((current) => !current)}
            >
              How you align <Icon name="chevron" />
            </button>
          )}
        </div>
        {job.alignment && (
          <div className="note" hidden={!alignOpen}>
            <div className="lab">How you align</div>
            {job.alignment}
          </div>
        )}
        <Contacts company={company} jobKey={job.key} otherJobs={otherJobs} ctx={ctx} id={id} />
      </div>
    </article>
  )
}
