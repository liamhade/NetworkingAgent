import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CompanyResult, PinMap, SearchResults, StatusMap } from '@/api'
import { ToastProvider } from '@/components/toast'
import { Results } from '@/pages/results'
import { emptyPins, emptyStatuses } from '@/test/fixtures'

/**
 * The results page: company panels (the top one open), jobs and people side by side,
 * filters, grouping, the message drawer, and "Find people" buttons that each call the
 * on-demand people endpoint with their own loading / error state.
 */

const company = (name: string, extra: Partial<CompanyResult> = {}): CompanyResult => ({
  name,
  url: `https://${name.toLowerCase()}.example`,
  description: `${name} builds things.`,
  alignment: 'You fit.',
  jobs: [
    {
      title: 'Data Analyst',
      url: `https://jobs.example/${name.toLowerCase()}`,
      location: 'NYC',
      salary: '',
      alignment: 'Matches your SQL.',
      score: 72,
      key: `job:${name.toLowerCase()}`,
    },
  ],
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
  summary: 'Ranked companies.',
  companies: [company('Acme', { score: 90 }), company('Globex', { score: 70 })],
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

const card = (name: string) =>
  screen.getAllByRole('article').find((article) => within(article).queryByText(name))!

/** The collapsed/expanded header button of a company panel. */
const panelToggle = (name: string) =>
  within(card(name)).getByRole('button', { name: new RegExp(`^${name}`), expanded: undefined })

async function expand(user: ReturnType<typeof userEvent.setup>, name: string) {
  const toggle = panelToggle(name)
  if (toggle.getAttribute('aria-expanded') !== 'true') await user.click(toggle)
}

const companyButton = (label: string, name: string) =>
  screen.getByRole('button', { name: `${label}: ${name}` })

const jobButton = (name: string) =>
  screen.getByRole('button', { name: `Find people for this role: Data Analyst at ${name}` })

afterEach(() => vi.unstubAllGlobals())

describe('results layout', () => {
  it('ranks the companies with fit scores and opens only the top one', () => {
    stubFetch()
    render(<Harness />)
    const names = screen.getAllByRole('article').map((a) => a.querySelector('.cn')?.textContent)
    expect(names).toEqual(['Acme', 'Globex'])
    expect(within(card('Acme')).getByText('#1')).toBeInTheDocument()
    expect(within(card('Acme')).getByText('Strong fit')).toBeInTheDocument()
    expect(within(card('Globex')).getByText('Good fit')).toBeInTheDocument()
    expect(panelToggle('Acme')).toHaveAttribute('aria-expanded', 'true')
    expect(panelToggle('Globex')).toHaveAttribute('aria-expanded', 'false')
    expect(within(card('Acme')).getByRole('region', { name: 'Jobs at Acme' })).toBeInTheDocument()
    expect(within(card('Globex')).queryByRole('region', { name: 'Jobs at Globex' })).toBeNull()
  })

  it('summarises the search and expands / collapses every panel', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness statuses={{ job: { 'job:acme': true }, person: {} }} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Analyst roles')
    const totals = screen.getByRole('list', { name: 'Search totals' })
    expect(within(totals).getByText('1 applied')).toBeInTheDocument()
    expect(screen.getByText('Ranked companies.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Expand all' }))
    expect(panelToggle('Globex')).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('button', { name: 'Collapse all' }))
    expect(panelToggle('Acme')).toHaveAttribute('aria-expanded', 'false')
  })

  it('filters companies, and offers to clear filters when none match', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Strong fit 75+' }))
    expect(screen.getAllByRole('article')).toHaveLength(1)
    expect(screen.getByText(/Showing 1 of 2 companies/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Has contact' }))
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getAllByRole('article')).toHaveLength(2)
  })

  it('sorts by name and groups by type', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={{
          summary: '',
          companies: [company('Zeta', { score: 90 }), company('Acme', { score: 60 })],
        }}
      />,
    )
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort' }), 'Name A-Z')
    const names = screen.getAllByRole('article').map((a) => a.querySelector('.cn')?.textContent)
    expect(names).toEqual(['Acme', 'Zeta'])

    await user.click(screen.getByRole('button', { name: 'Type' }))
    expect(screen.getByRole('heading', { name: /^Jobs/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^People/ })).toBeInTheDocument()
    // Each job carries a tag back to its company.
    await user.click(screen.getAllByRole('button', { name: 'Zeta' })[0])
    expect(panelToggle('Zeta')).toHaveAttribute('aria-expanded', 'true')
  })
})

describe('shared background', () => {
  it('shows why a person was found on their card, only when there is one', () => {
    stubFetch()
    const ann = { ...person('Ann'), shared_background: 'Same school: Cornell University' }
    render(
      <Harness
        initial={{ summary: '', companies: [company('Acme', { people: [ann, person('Bob')] })] }}
      />,
    )
    expect(screen.getAllByText('Same school: Cornell University')).toHaveLength(1)
  })
})

describe('message drawer', () => {
  it('opens with the example message, counts characters and marks connected', async () => {
    stubFetch()
    const onToggleStatus = vi.fn()
    const user = userEvent.setup()
    render(
      <Harness
        onToggleStatus={onToggleStatus}
        initial={{ summary: '', companies: [company('Acme', { people: [person('Ann')] })] }}
      />,
    )
    await user.click(screen.getByRole('button', { name: /^Message Ann →?/ }))
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

  it('"Start here" drafts a message to the top contact', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <Harness
        initial={{
          summary: '',
          companies: [company('Acme'), company('Globex', { people: [person('Gina')] })],
        }}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Draft message' }))
    expect(screen.getByRole('dialog', { name: 'Message Gina' })).toBeInTheDocument()
  })
})

describe('pins on the results page', () => {
  it('pins with an undo toast', async () => {
    stubFetch()
    const onTogglePin = vi.fn()
    const user = userEvent.setup()
    render(<Harness onTogglePin={onTogglePin} />)
    await user.click(screen.getByRole('button', { name: 'Pin Globex' }))
    expect(onTogglePin).toHaveBeenLastCalledWith('company', 'company:globex', true)
    expect(screen.getByRole('status')).toHaveTextContent('Pinned Globex')
    await user.click(screen.getByRole('button', { name: 'Undo' }))
    expect(onTogglePin).toHaveBeenLastCalledWith('company', 'company:globex', false)
  })
})

describe('Find people', () => {
  it('offers buttons for the company and for each job', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    expect(companyButton('Find people to connect with', 'Acme')).toBeEnabled()
    expect(jobButton('Acme')).toBeEnabled()
    await expand(user, 'Globex')
    expect(jobButton('Globex')).toBeEnabled()
  })

  it('calls the API for the company, or for the job', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(companyButton('Find people to connect with', 'Acme'))
    await expand(user, 'Globex')
    await user.click(jobButton('Globex'))
    expect(pending.map((p) => [p.url, p.body])).toEqual([
      ['/api/searches/s1/people', { company_key: 'company:acme', job_key: null }],
      ['/api/searches/s1/people', { company_key: 'company:globex', job_key: 'job:globex' }],
    ])
  })

  it('runs two searches at once, each with its own loading state, and inserts the people', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await expand(user, 'Globex')

    await user.click(companyButton('Find people to connect with', 'Acme'))
    await user.click(companyButton('Find people to connect with', 'Globex'))
    expect(pending).toHaveLength(2)
    expect(companyButton('Find people to connect with', 'Acme')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(within(card('Acme')).getByText('Searching LinkedIn…')).toBeInTheDocument()

    // Globex answers first; Acme is still loading.
    pending[1].resolve(
      json(company('Globex', { score: 70, people: [person('Gina')], people_searched: true })),
    )
    await within(card('Globex')).findByText('Gina')
    expect(within(card('Globex')).getByText('Gina hires analysts.')).toBeInTheDocument()
    expect(
      within(card('Globex')).getByRole('button', { name: 'Mark connected: Gina' }),
    ).toHaveAttribute('aria-pressed', 'false')
    expect(within(card('Globex')).getByRole('button', { name: 'Pin Gina' })).toBeInTheDocument()
    expect(companyButton('Find people to connect with', 'Acme')).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(companyButton('Find more people', 'Globex')).toBeEnabled()

    pending[0].resolve(
      json(company('Acme', { score: 90, people: [person('Ann')], people_searched: true })),
    )
    await within(card('Acme')).findByText('Ann')
    expect(within(card('Globex')).getByText('Gina')).toBeInTheDocument()
  })

  it('says when nobody was found', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(companyButton('Find people to connect with', 'Acme'))
    pending[0].resolve(json(company('Acme', { score: 90, people_searched: true })))
    await within(card('Acme')).findByText('No current employees found yet.')
  })

  it('shows an error with a retry, per button', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await expand(user, 'Globex')
    await user.click(companyButton('Find people to connect with', 'Acme'))
    pending[0].resolve(json({ detail: 'Google is unavailable.' }, 500))

    const alert = await within(card('Acme')).findByRole('alert')
    expect(alert).toHaveTextContent('Google is unavailable.')
    expect(within(card('Globex')).queryByRole('alert')).not.toBeInTheDocument()

    await user.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(pending).toHaveLength(2)
    await waitFor(() => expect(within(card('Acme')).queryByRole('alert')).not.toBeInTheDocument())
    pending[1].resolve(json(company('Acme', { people: [person('Ann')], people_searched: true })))
    await within(card('Acme')).findByText('Ann')
  })

  it('is disabled until the search is saved', () => {
    stubFetch()
    render(<Harness searchId={null} />)
    expect(companyButton('Find people to connect with', 'Acme')).toBeDisabled()
  })
})
