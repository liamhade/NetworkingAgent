import { useState } from 'react'
import type { CompanyResult, PersonResult } from '@/api'
import { FindPeopleButton, FindPeopleSearch } from '@/components/find-people-button'
import { Icon } from '@/components/icon'
import { PinToggle } from '@/components/pin-toggle'
import { StatusToggle } from '@/components/status-toggle'
import { cx } from '@/utils/cx'
import { initials } from '@/utils/initials'
import type { RowContext } from './row-context'

/** Contacts shown before "Show N more". */
const PEOPLE_LIMIT = 3

const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name
const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

function PersonRow({
  person,
  company,
  ctx,
}: {
  person: PersonResult
  company: CompanyResult
  ctx: RowContext
}) {
  const [noteOpen, setNoteOpen] = useState(false)
  const pinned = !!person.key && !!ctx.pins.person[person.key]
  const connected = !!person.key && !!ctx.statuses.person[person.key]
  return (
    <li className={cx('row', pinned && 'pinned', connected && 'done')}>
      <div className="rtop">
        <span className="pavatar" aria-hidden="true">
          {initials(person.name)}
        </span>
        <div className="rmain">
          {person.profile_url ? (
            <a className="rtitle" href={person.profile_url} target="_blank" rel="noreferrer">
              {person.name}
              <Icon name="ext" />
              <span className="sr"> (opens LinkedIn profile)</span>
            </a>
          ) : (
            <span className="rtitle plain">{person.name}</span>
          )}
          <div className="rmeta">
            {person.title && <span>{person.title}</span>}
            {person.shared_background && (
              <span className="pill per tight">{person.shared_background}</span>
            )}
          </div>
        </div>
        {person.key && (
          <PinToggle
            name={person.name}
            isPinned={pinned}
            onChange={(value) => ctx.pin('person', person.key, person.name, value)}
          />
        )}
      </div>
      {(person.key || person.alignment) && (
        <div className="ract">
          {person.key && (
            <StatusToggle
              kind="person"
              name={person.name}
              isSelected={connected}
              onChange={(value) => ctx.onToggleStatus('person', person.key, value)}
            />
          )}
          {person.alignment && (
            <button
              type="button"
              className="disc"
              aria-expanded={noteOpen}
              onClick={() => setNoteOpen((current) => !current)}
            >
              Why connect <Icon name="chevron" />
            </button>
          )}
        </div>
      )}
      {person.alignment && (
        <div className="note p" hidden={!noteOpen}>
          <div className="lab">Why connect</div>
          {person.alignment}
        </div>
      )}
      <div className="crosslink">
        <button type="button" className="xlink per" onClick={() => ctx.message(person, company)}>
          <Icon name="send" />
          Message {firstName(person.name)} <Icon name="arrow" />
        </button>
      </div>
    </li>
  )
}

/**
 * The company's people on a job card: a count line that opens the list, or the
 * "Find people" button when nobody has been searched for yet. People belong to the
 * company, so every card of that company shows the same ones.
 */
export function Contacts({
  company,
  jobKey,
  otherJobs,
  ctx,
  id,
}: {
  company: CompanyResult
  jobKey: string
  /** How many other jobs of this company are in the list. */
  otherJobs: number
  ctx: RowContext
  id: string
}) {
  const [open, setOpen] = useState(false)
  const [all, setAll] = useState(false)
  const { people } = company

  if (people.length === 0) {
    if (company.people_searched) {
      return <div className="contacts none">No contacts found at {company.name} yet.</div>
    }
    if (!company.key) return null
    return (
      <div className="contacts">
        <FindPeopleButton
          searchId={ctx.searchId}
          companyKey={company.key}
          jobKey={jobKey || undefined}
          target={company.name}
          label="Find people"
          onFound={ctx.onCompanyFound}
        />
      </div>
    )
  }

  const shown = all ? people : people.slice(0, PEOPLE_LIMIT)
  const hidden = people.length - shown.length
  const listId = `${id}-contacts`
  return (
    <div className="contacts">
      <button
        type="button"
        className="disc"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="avs" aria-hidden="true">
          {people.slice(0, 3).map((person, index) => (
            <span className="pavatar" key={index}>
              {initials(person.name)}
            </span>
          ))}
        </span>
        {plural(people.length, 'contact', 'contacts')} at {company.name}
        {otherJobs > 0 && ` · shared with ${plural(otherJobs, 'other job', 'other jobs')}`}
        <Icon name="chevron" />
      </button>
      {open && (
        <div className="cpeople" id={listId}>
          <ul className="rows">
            {shown.map((person, index) => (
              <PersonRow
                key={`${person.key || person.profile_url}-${index}`}
                person={person}
                company={company}
                ctx={ctx}
              />
            ))}
          </ul>
          <div className="cfoot">
            {hidden > 0 && (
              <button type="button" className="btn xs" onClick={() => setAll(true)}>
                Show {plural(hidden, 'more person', 'more people')}
                <Icon name="chevron" size="sm" />
              </button>
            )}
            {company.key && (
              <FindPeopleSearch
                searchId={ctx.searchId}
                companyKey={company.key}
                target={company.name}
                label="Find more people"
                onFound={ctx.onCompanyFound}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
