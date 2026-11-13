import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CompanyResult, SearchResults } from '@/api'
import { Results } from '@/pages/results'
import { emptyPins, emptyStatuses } from '@/test/fixtures'

/**
 * "Find People To Connect With" on the results page: each button calls the on-demand
 * people endpoint, keeps its own loading / error state, and inserts the people it finds.
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
      key: `job:${name.toLowerCase()}`,
    },
  ],
  people: [],
  people_searched: false,
  key: `company:${name.toLowerCase()}`,
  ...extra,
})

const RESULTS: SearchResults = {
  summary: 'Ranked companies.',
  companies: [company('Acme', { score: 90 }), company('Globex', { score: 70 })],
}

const person = (name: string) => ({
  name,
  title: 'Recruiter',
  profile_url: `https://linkedin.com/in/${name.toLowerCase()}`,
  alignment: `${name} hires analysts.`,
  connect_message: `Hi ${name}, would love to connect.`,
  key: `person:${name.toLowerCase()}`,
})

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

function Harness({ searchId = 's1' }: { searchId?: string | null }) {
  const [results, setResults] = useState(RESULTS)
  return (
    <Results
      statuses={[]}
      results={results}
      error={null}
      running={false}
      entityStatuses={emptyStatuses()}
      statusError={null}
      onToggleStatus={vi.fn()}
      pins={emptyPins()}
      pinError={null}
      onTogglePin={vi.fn()}
      searchId={searchId}
      onCompanyFound={(found) =>
        setResults((current) => ({
          ...current,
          companies: current.companies.map((c) => (c.key === found.key ? found : c)),
        }))
      }
      onBack={vi.fn()}
    />
  )
}

const card = (name: string) =>
  screen.getAllByRole('article').find((article) => within(article).queryByText(name))!

const companyButton = (name: string) =>
  screen.getByRole('button', { name: `Find People To Connect With: ${name}` })

afterEach(() => vi.unstubAllGlobals())

describe('Find People To Connect With', () => {
  it('shows companies in ranked order with a fit score and buttons under companies and jobs', () => {
    stubFetch()
    render(<Harness />)
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual(['1. Acme', '2. Globex'])
    expect(within(card('Acme')).getByText('Fit 90')).toBeInTheDocument()
    expect(companyButton('Acme')).toBeEnabled()
    expect(
      screen.getByRole('button', { name: 'Find People To Connect With: Data Analyst at Acme' }),
    ).toBeEnabled()
  })

  it('calls the API for the company, or for the job', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(companyButton('Acme'))
    await user.click(
      screen.getByRole('button', { name: 'Find People To Connect With: Data Analyst at Globex' }),
    )
    expect(pending.map((p) => [p.url, p.body])).toEqual([
      ['/api/searches/s1/people', { company_key: 'company:acme', job_key: null }],
      ['/api/searches/s1/people', { company_key: 'company:globex', job_key: 'job:globex' }],
    ])
  })

  it('runs two searches at once, each with its own loading state, and inserts the people', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(companyButton('Acme'))
    await user.click(companyButton('Globex'))
    expect(pending).toHaveLength(2)
    expect(companyButton('Acme')).toHaveAttribute('aria-busy', 'true')
    expect(companyButton('Globex')).toHaveAttribute('aria-busy', 'true')
    expect(within(card('Acme')).getByText('Finding people…')).toBeInTheDocument()

    // Globex answers first; Acme is still loading.
    pending[1].resolve(
      json(company('Globex', { score: 70, people: [person('Gina')], people_searched: true })),
    )
    await within(card('Globex')).findByText('Gina')
    expect(within(card('Globex')).getByText('Gina hires analysts.')).toBeInTheDocument()
    expect(within(card('Globex')).getByText('Hi Gina, would love to connect.')).toBeInTheDocument()
    expect(within(card('Globex')).getByRole('button', { name: 'NOT CONNECTED' })).toBeInTheDocument()
    expect(within(card('Globex')).getByRole('button', { name: 'Pin Gina' })).toBeInTheDocument()
    expect(companyButton('Acme')).toHaveAttribute('aria-busy', 'true')
    expect(
      screen.getByRole('button', { name: 'Find more people: Globex' }),
    ).toBeEnabled()

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
    await user.click(companyButton('Acme'))
    pending[0].resolve(json(company('Acme', { score: 90, people_searched: true })))
    await within(card('Acme')).findByText('No current employees found yet.')
  })

  it('shows an error with a retry, per button', async () => {
    const pending = stubFetch()
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(companyButton('Acme'))
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
    expect(companyButton('Acme')).toBeDisabled()
  })
})
