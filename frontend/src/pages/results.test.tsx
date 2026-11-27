import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CompanyResult, JobResult, PinMap, SearchResults, StatusMap } from '@/api'
import { ToastProvider } from '@/components/toast'
import { Results } from '@/pages/results'
import { emptyPins, emptyStatuses } from '@/test/fixtures'

/**
 * The results page: one ranked card per job, contacts at the company on each card,
 * filters (including the company multi-select), sorts, stats, the message drawer, and
 * "Find people" buttons that call the on-demand people endpoint.
 */

const job = (title: string, extra: Partial<JobResult> = {}): JobResult => ({
  title,
  url: `https://jobs.example/${title.toLowerCase().replaceAll(' ', '-')}`,
  location: 'NYC',
  salary: '',
  alignment: 'Matches your SQL.',
  score: 72,
  key: `job:${title.toLowerCase().replaceAll(' ', '-')}`,
  ...extra,
})

const company = (name: string, extra: Partial<CompanyResult> = {}): CompanyResult => ({
  name,
  url: `https://${name.toLowerCase()}.example`,
  description: `${name} builds things.`,
  alignment: 'You fit.',
  jobs: [job(`${name} Analyst`)],
  people: [],
  people_searched: false,
  key: `company:${name.toLowerCase()}`,
  ...extra,
})

const person = (name: string) => ({
  name,
  title: 'Recruiter',
  profile_url: `https://linkedin.com/in/${name.toLowerCase()}`,
  alignment: `${name} hires analysts.`,
  connect_message: `Hi ${name}, would love to connect.`,
  key: `person:${name.toLowerCase()}`,
})

const RESULTS: SearchResults = {
  summary: 'Ranked jobs.',
  companies: [
    company('Acme', { score: 90, jobs: [job('Acme Analyst', { rank: 1, score: 90 })] }),
    company('Globex', { score: 70, jobs: [job('Globex Analyst', { rank: 2, score: 70 })] }),
  ],
}

interface Pending {
  url: string
  body: { company_key: string; job_key: string | null }
  resolve: (response: Response) => void
}

/** `fetch` that holds every request until the test answers it. */
function stubFetch() {
  const pending: Pending[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(
      (input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((resolve) =>
          pending.push({ url: String(input), body: JSON.parse(String(init?.body)), resolve }),
        ),
    ),
  )
  return pending
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

interface HarnessProps {
  searchId?: string | null
  initial?: SearchResults
  statuses?: StatusMap
  pins?: PinMap
  onToggleStatus?: () => void
  onTogglePin?: () => void
}

function Harness({
  searchId = 's1',
  initial = RESULTS,
  statuses = emptyStatuses(),
  pins = emptyPins(),
  onToggleStatus = vi.fn(),
  onTogglePin = vi.fn(),
}: HarnessProps) {
  const [results, setResults] = useState(initial)
  return (
    <ToastProvider>
      <Results
        results={results}
        meta={{ title: 'Analyst roles', location: 'NYC', createdAt: null, boards: ['Built In NYC'] }}
        entityStatuses={statuses}
        statusError={null}
        onToggleStatus={onToggleStatus}
        pins={pins}
        pinError={null}
        onTogglePin={onTogglePin}
        searchId={searchId}
        onCompanyFound={(found) =>
          setResults((current) => ({
            ...current,
            companies: current.companies.map((c) => (c.key === found.key ? found : c)),
          }))
        }
        onEdit={vi.fn()}
        onNewSearch={vi.fn()}
      />
    </ToastProvider>
  )
}

const searchOf = (...companies: CompanyResult[]): SearchResults => ({ summary: '', companies })

/** Titles of the job cards, top to bottom. */
const titles = () =>
  screen.getAllByRole('article').map((a) => a.querySelector('.rtitle')?.textContent?.replace(/ \(.*/, ''))

const card = (title: string) =>
  screen.getAllByRole('article').find((article) => within(article).queryByText(title, { exact: false }))!

const findButton = (name: string) => screen.getByRole('button', { name: `Find people: ${name}` })

const filter = (label: string) => screen.getByRole('button', { name: label })
const sortBy = (user: ReturnType<typeof userEvent.setup>, label: string) =>
  user.selectOptions(screen.getByRole('combobox', { name: 'Sort' }), label)
const companyList = () => screen.getByRole('navigation', { name: 'Companies' })

afterEach(() => vi.unstubAllGlobals())

describe('ranking', () => {
  it('lists one card per job in the ranker order, with its rank', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(
          company('Acme', {
            jobs: [job('Second', { rank: 2, score: 95 }), job('Fourth', { rank: 4, score: 60 })],
          }),
          company('Globex', {
            jobs: [job('First', { rank: 1, score: 70 }), job('Third', { rank: 3, score: 80 })],
          }),
        )}
      />,
    )
    expect(titles()).toEqual(['First', 'Second', 'Third', 'Fourth'])
    expect(within(card('First')).getByLabelText('Rank 1')).toHaveTextContent('#1')
    expect(within(card('Fourth')).getByLabelText('Rank 4')).toHaveTextContent('#4')
    expect(screen.getByText('Showing 4 of 4 jobs')).toBeInTheDocument()
  })

  it('orders a search saved without ranks by score, then company, then job order', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(
          company('Acme', { jobs: [job('A1', { score: 70 }), job('A2', { score: 80 })] }),
          company('Globex', { jobs: [job('G1', { score: 80 }), job('G2', { score: null })] }),
        )}
      />,
    )
    expect(titles()).toEqual(['A2', 'G1', 'A1', 'G2'])
    expect(within(card('G2')).getByLabelText('Rank 4')).toBeInTheDocument()
  })

  it('shows the facts of a job and its reason, with the alignment note expandable', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={searchOf(
          company('Acme', {
            score: 88,
            jobs: [
              job('Data Analyst', {
                rank: 1,
                score: 88,
                salary: '$120k',
                years_required: '3-5 years',
                reason: 'Your SQL work lines up.',
              }),
            ],
          }),
        )}
      />,
    )
    const analyst = card('Data Analyst')
    expect(within(analyst).getByRole('link', { name: /Data Analyst/ })).toHaveAttribute(
      'href',
      'https://jobs.example/data-analyst',
    )
    expect(within(analyst).getByRole('link', { name: /Open posting/ })).toHaveAttribute(
      'href',
      'https://jobs.example/data-analyst',
    )
    expect(within(analyst).getByRole('button', { name: 'Acme' })).toBeInTheDocument()
    expect(within(analyst).getByText('NYC')).toBeInTheDocument()
    expect(within(analyst).getByText('$120k')).toBeInTheDocument()
    expect(within(analyst).getByText('3-5 years')).toBeInTheDocument()
    expect(within(analyst).getByText('Strong fit')).toBeInTheDocument()
    expect(within(analyst).getByText('Your SQL work lines up.')).toBeInTheDocument()
    const align = within(analyst).getByRole('button', { name: /How you align/ })
    expect(align).toHaveAttribute('aria-expanded', 'false')
    expect(within(analyst).getByText('Matches your SQL.')).not.toBeVisible()
    await user.click(align)
    expect(within(analyst).getByText('Matches your SQL.')).toBeVisible()
  })

  it('opens an old saved search whose jobs have no rank, reason or years', () => {
    stubFetch()
    const old = company('Acme', { score: undefined })
    delete (old.jobs[0] as Partial<JobResult>).score
    render(<Harness initial={searchOf(old)} />)
    expect(titles()).toEqual(['Acme Analyst'])
    expect(within(card('Acme Analyst')).getByLabelText('Rank 1')).toBeInTheDocument()
  })
})

describe('stats and layout', () => {
  it('summarises the search, jobs first', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(
          company('Acme', { people: [person('Ann'), person('Bob')] }),
          company('Globex'),
        )}
        statuses={{ job: { 'job:acme-analyst': true }, person: { 'person:ann': true } }}
        pins={{ company: {}, job: { 'job:globex-analyst': true }, person: { 'person:bob': true } }}
      />,
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Analyst roles')
    const items = within(screen.getByRole('list', { name: 'Search totals' })).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      '2Jobs',
      '2Companies',
      '2Contacts',
      '1Applied',
      '1Connected',
      '2Pinned',
    ])
  })

  it('hides, resizes and remembers the sidebar', async () => {
    stubFetch()
    localStorage.removeItem('na-results-rail')
    localStorage.removeItem('na-results-rail-width')
    const user = userEvent.setup()
    const { unmount } = render(<Harness />)
    const handle = screen.getByRole('separator', { name: 'Resize filters' })
    fireEvent.keyDown(handle, { key: 'ArrowRight' })
    expect(handle).toHaveAttribute('aria-valuenow', '236')
    expect(localStorage.getItem('na-results-rail-width')).toBe('236')
    await user.click(screen.getByRole('button', { name: 'Hide filters' }))
    expect(screen.queryByRole('separator', { name: 'Resize filters' })).toBeNull()
    expect(screen.queryByRole('toolbar', { name: 'View options' })).toBeNull()
    unmount()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Show filters' }))
    expect(screen.getByRole('toolbar', { name: 'View options' })).toBeInTheDocument()
    expect(localStorage.getItem('na-results-rail')).toBe('open')
  })

  it('has no company or type view, panels, or expand / collapse all', () => {
    stubFetch()
    render(<Harness />)
    expect(screen.queryByRole('button', { name: 'Type' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Expand all' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Collapse all' })).toBeNull()
  })

  it('shows companies without matching jobs in their own section', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(company('Acme'), company('Empty Co', { jobs: [], description: 'Quiet.' }))}
      />,
    )
    expect(titles()).toEqual(['Acme Analyst'])
    const section = screen.getByRole('region', { name: 'Companies without matching jobs' })
    expect(within(section).getByText('Empty Co', { exact: false })).toBeInTheDocument()
    expect(within(section).getByText('Quiet.')).toBeInTheDocument()
  })

  it('keeps listed companies without any job instead of an empty-state', () => {
    stubFetch()
    render(<Harness initial={searchOf(company('Empty Co', { jobs: [] }))} />)
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(screen.getByRole('region', { name: 'Companies without matching jobs' })).toBeInTheDocument()
    expect(screen.getByText('Showing 0 of 0 jobs')).toBeInTheDocument()
  })

  it('says so when nothing was found at all', () => {
    stubFetch()
    render(<Harness initial={searchOf()} />)
    expect(screen.getByText('No matching jobs found')).toBeInTheDocument()
  })
})

describe('filters', () => {
  const MIXED = searchOf(
    company('Acme', {
      people: [person('Ann')],
      jobs: [job('Strong One', { rank: 1, score: 90 })],
    }),
    company('Globex', { jobs: [job('Weak One', { rank: 2, score: 60 })] }),
    company('Initech', { jobs: [job('Mid One', { rank: 3, score: 75 })] }),
  )

  it('Strong fit 75+ keeps jobs scoring 75 or more', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={MIXED} />)
    await user.click(filter('Strong fit 75+'))
    expect(titles()).toEqual(['Strong One', 'Mid One'])
    expect(screen.getByText('Showing 2 of 3 jobs')).toBeInTheDocument()
  })

  it('Has contacts keeps jobs at companies with people', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={MIXED} />)
    await user.click(filter('Has contacts'))
    expect(titles()).toEqual(['Strong One'])
  })

  it('Not applied hides jobs marked applied', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={MIXED} statuses={{ job: { 'job:strong-one': true }, person: {} }} />)
    await user.click(filter('Not applied'))
    expect(titles()).toEqual(['Weak One', 'Mid One'])
  })

  it('Pinned keeps pinned jobs', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={MIXED} pins={{ company: {}, job: { 'job:mid-one': true }, person: {} }} />)
    await user.click(filter('Pinned'))
    expect(titles()).toEqual(['Mid One'])
  })

  it('combines filters and offers to clear them when none match', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={MIXED} />)
    await user.click(filter('Has contacts'))
    await user.click(filter('Pinned'))
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(screen.getByText('No jobs match these filters')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getAllByRole('article')).toHaveLength(3)
  })

  it('lists companies with job counts and multi-selects them', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={searchOf(
          company('Acme', { jobs: [job('A1', { rank: 1 }), job('A2', { rank: 3 })] }),
          company('Globex', { jobs: [job('G1', { rank: 2 })] }),
          company('Initech', { jobs: [job('I1', { rank: 4 })] }),
        )}
      />,
    )
    const list = within(companyList())
    expect(list.getByRole('button', { name: 'Acme 2' })).toHaveAttribute('aria-pressed', 'false')
    expect(list.getByRole('button', { name: 'Globex 1' })).toBeInTheDocument()

    await user.click(list.getByRole('button', { name: 'Acme 2' }))
    expect(titles()).toEqual(['A1', 'A2'])
    await user.click(list.getByRole('button', { name: 'Initech 1' }))
    expect(titles()).toEqual(['A1', 'A2', 'I1'])
    expect(list.getByRole('button', { name: 'Acme 2' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(list.getByRole('button', { name: 'Acme 2' }))
    expect(titles()).toEqual(['I1'])
  })

  it('toggles the company filter from the company tag and shows its description and score', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    const tag = within(card('Globex Analyst')).getByRole('button', { name: 'Globex' })
    expect(tag).toHaveAttribute('title', 'Globex builds things. · Score 70')
    expect(within(companyList()).getByRole('button', { name: 'Globex 1' })).toHaveAttribute(
      'title',
      'Globex builds things. · Score 70',
    )
    await user.click(tag)
    expect(titles()).toEqual(['Globex Analyst'])
    expect(tag).toHaveAttribute('aria-pressed', 'true')
    await user.click(tag)
    expect(titles()).toEqual(['Acme Analyst', 'Globex Analyst'])
  })
})

describe('sorts', () => {
  const SORTABLE = searchOf(
    company('Zeta', {
      jobs: [job('Z Senior', { rank: 1, years_required: '5+ years' })],
    }),
    company('Acme', {
      jobs: [
        job('A Unknown', { rank: 2 }),
        job('A Junior', { rank: 3, years_required: '0-2 years' }),
      ],
    }),
    company('Mid', { jobs: [job('M Mid', { rank: 4, years_required: '3 years' })] }),
  )

  it('defaults to Best fit', () => {
    stubFetch()
    render(<Harness initial={SORTABLE} />)
    expect(screen.getByRole('combobox', { name: 'Sort' })).toHaveValue('fit')
    expect(titles()).toEqual(['Z Senior', 'A Unknown', 'A Junior', 'M Mid'])
  })

  it('Pinned first puts pinned jobs on top, keeping rank order within each group', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={SORTABLE}
        pins={{ company: {}, job: { 'job:m-mid': true, 'job:a-unknown': true }, person: {} }}
      />,
    )
    await sortBy(user, 'Pinned first')
    expect(titles()).toEqual(['A Unknown', 'M Mid', 'Z Senior', 'A Junior'])
  })

  it('Least experience required sorts by the smallest years, unknown last', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={SORTABLE} />)
    await sortBy(user, 'Least experience required')
    expect(titles()).toEqual(['A Junior', 'M Mid', 'Z Senior', 'A Unknown'])
  })

  it('Company A-Z sorts by company name, then rank', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={SORTABLE} />)
    await sortBy(user, 'Company A-Z')
    expect(titles()).toEqual(['A Unknown', 'A Junior', 'M Mid', 'Z Senior'])
    // Rank numbers stay the Best-fit positions.
    expect(within(card('Z Senior')).getByLabelText('Rank 1')).toBeInTheDocument()
  })
})

describe('contacts on a card', () => {
  it('counts the contacts at the company and expands them', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={searchOf(
          company('Ro', { people: [person('Ann'), person('Bob'), person('Cy'), person('Di')] }),
        )}
      />,
    )
    const toggle = within(card('Ro Analyst')).getByRole('button', { name: /4 contacts at Ro/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).not.toHaveTextContent('shared with')
    expect(screen.queryByText('Ann')).toBeNull()
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Ann')).toBeInTheDocument()
    expect(screen.getByText('Cy')).toBeInTheDocument()
    expect(screen.queryByText('Di')).toBeNull()
    await user.click(screen.getByRole('button', { name: /Show 1 more person/ }))
    expect(screen.getByText('Di')).toBeInTheDocument()
  })

  it('says when the contacts are shared with the same company\'s other jobs', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(
          company('Ro', {
            people: [person('Ann'), person('Bob'), person('Cy')],
            jobs: [job('One', { rank: 1 }), job('Two', { rank: 2 }), job('Three', { rank: 3 })],
          }),
          company('Solo', { people: [person('Di')] }),
        )}
      />,
    )
    expect(
      within(card('Three')).getByRole('button', {
        name: '3 contacts at Ro · shared with 2 other jobs',
      }),
    ).toBeInTheDocument()
    expect(
      within(card('Solo Analyst')).getByRole('button', { name: '1 contact at Solo' }),
    ).toBeInTheDocument()
  })

  it('counts only the other jobs in the whole list, not those hidden by a filter', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={searchOf(
          company('Ro', {
            people: [person('Ann')],
            jobs: [job('Hi', { rank: 1, score: 90 }), job('Lo', { rank: 2, score: 50 })],
          }),
        )}
      />,
    )
    await user.click(filter('Strong fit 75+'))
    expect(
      within(card('Hi')).getByRole('button', { name: '1 contact at Ro · shared with 1 other job' }),
    ).toBeInTheDocument()
  })

  it('opens the message drawer with the example message and marks connected', async () => {
    stubFetch()
    const onToggleStatus = vi.fn()
    const user = userEvent.setup()
    render(
      <Harness
        onToggleStatus={onToggleStatus}
        initial={searchOf(company('Acme', { people: [person('Ann')] }))}
      />,
    )
    await user.click(screen.getByRole('button', { name: /1 contact at Acme/ }))
    await user.click(screen.getByRole('button', { name: /^Message Ann/ }))
    const dialog = screen.getByRole('dialog', { name: 'Message Ann' })
    expect(within(dialog).getByRole('textbox', { name: 'Example LinkedIn message' })).toHaveValue(
      'Hi Ann, would love to connect.',
    )
    expect(within(dialog).getByText('30 / 300')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: /open linkedin/i })).toHaveAttribute(
      'href',
      'https://linkedin.com/in/ann',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Mark connected: Ann' }))
    expect(onToggleStatus).toHaveBeenCalledWith('person', 'person:ann', true)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Message Ann' })).toBeNull()
  })

  it('shows why a person was found, only when there is a reason', async () => {
    stubFetch()
    const user = userEvent.setup()
    const ann = { ...person('Ann'), shared_background: 'Same school: Cornell University' }
    render(<Harness initial={searchOf(company('Acme', { people: [ann, person('Bob')] }))} />)
    await user.click(screen.getByRole('button', { name: /2 contacts at Acme/ }))
    expect(screen.getAllByText('Same school: Cornell University')).toHaveLength(1)
  })
})

describe('applied and pins on a card', () => {
  it('marks a job applied', async () => {
    stubFetch()
    const onToggleStatus = vi.fn()
    const user = userEvent.setup()
    render(<Harness onToggleStatus={onToggleStatus} />)
    await user.click(
      within(card('Acme Analyst')).getByRole('button', { name: /Mark applied: Acme Analyst/ }),
    )
    expect(onToggleStatus).toHaveBeenCalledWith('job', 'job:acme-analyst', true)
  })

  it('pins a job with an undo toast', async () => {
    stubFetch()
    const onTogglePin = vi.fn()
    const user = userEvent.setup()
    render(<Harness onTogglePin={onTogglePin} />)
    await user.click(screen.getByRole('button', { name: 'Pin Globex Analyst' }))
    expect(onTogglePin).toHaveBeenLastCalledWith('job', 'job:globex-analyst', true)
    expect(screen.getByRole('status')).toHaveTextContent('Pinned Globex Analyst')
    await user.click(screen.getByRole('button', { name: 'Undo' }))
    expect(onTogglePin).toHaveBeenLastCalledWith('job', 'job:globex-analyst', false)
  })
})

describe('Find people on a card', () => {
  it('offers the button when people were not searched, and not when they were', () => {
    stubFetch()
    render(
      <Harness
        initial={searchOf(
          company('Acme'),
          company('Globex', { people_searched: true }),
        )}
      />,
    )
    expect(findButton('Acme')).toBeEnabled()
    expect(screen.queryByRole('button', { name: /Find people: Globex/ })).toBeNull()
    expect(within(card('Globex Analyst')).getByText(/No contacts found at Globex/)).toBeInTheDocument()
  })

  it('calls the API for the company with the card\'s job', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(findButton('Globex'))
    expect(pending.map((p) => [p.url, p.body])).toEqual([
      [
        '/api/searches/s1/people',
        { company_key: 'company:globex', job_key: 'job:globex-analyst', same_school: false },
      ],
    ])
  })

  it('updates every card of the company with the people it finds', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    const ro = company('Ro', { jobs: [job('One', { rank: 1 }), job('Two', { rank: 2 })] })
    render(<Harness initial={searchOf(ro)} />)
    const buttons = screen.getAllByRole('button', { name: 'Find people: Ro' })
    expect(buttons).toHaveLength(2)
    await user.click(buttons[0])
    expect(pending).toHaveLength(1)
    expect(buttons[0]).toHaveAttribute('aria-busy', 'true')

    pending[0].resolve(
      json({ ...ro, people: [person('Gina'), person('Hal')], people_searched: true }),
    )
    expect(
      await within(card('Two')).findByRole('button', {
        name: '2 contacts at Ro · shared with 1 other job',
      }),
    ).toBeInTheDocument()
    expect(within(card('One')).getByRole('button', { name: /2 contacts at Ro/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Find people: Ro' })).toBeNull()
  })

  it('offers more people from the expanded contacts, optionally from my school', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness initial={searchOf(company('Acme', { people: [person('Ann')], people_searched: true }))} />)
    await user.click(screen.getByRole('button', { name: /1 contact at Acme/ }))
    await user.click(screen.getByRole('checkbox', { name: 'Only people from my school' }))
    await user.click(screen.getByRole('button', { name: 'Find more people: Acme' }))
    expect(pending.map((p) => p.body)).toEqual([
      { company_key: 'company:acme', job_key: null, same_school: true },
    ])
  })

  it('says when nobody was found', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(findButton('Acme'))
    pending[0].resolve(json(company('Acme', { score: 90, people_searched: true })))
    await within(card('Acme Analyst')).findByText(/No contacts found at Acme/)
  })

  it('shows an error with a retry, on that card only', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(findButton('Acme'))
    pending[0].resolve(json({ detail: 'Google is unavailable.' }, 500))

    const alert = await within(card('Acme Analyst')).findByRole('alert')
    expect(alert).toHaveTextContent('Google is unavailable.')
    expect(within(card('Globex Analyst')).queryByRole('alert')).not.toBeInTheDocument()

    await user.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(pending).toHaveLength(2)
    await waitFor(() =>
      expect(within(card('Acme Analyst')).queryByRole('alert')).not.toBeInTheDocument(),
    )
    pending[1].resolve(json(company('Acme', { people: [person('Ann')], people_searched: true })))
    await within(card('Acme Analyst')).findByRole('button', { name: /1 contact at Acme/ })
  })

  it('is disabled until the search is saved', () => {
    stubFetch()
    render(<Harness searchId={null} />)
    expect(findButton('Acme')).toBeDisabled()
  })
})
