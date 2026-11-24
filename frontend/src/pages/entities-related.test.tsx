import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EntityKind } from '@/api'
import App from '@/App'
import { company, emptyPins, job, person } from '@/test/fixtures'

/** Related-entity links under company / job / person cards (mocked fetch, no network). */

const ENTITIES = {
  companies: [
    company('Acme', 0, { key: 'company:acme' }),
    company('Globex', 1, { key: 'company:globex' }),
    company('Empty Co', 2, { key: 'company:empty' }),
  ],
  jobs: [
    job('Engineer', 0, { company: 'Acme', company_key: 'company:acme' }),
    job('Designer', 1, { company: 'Globex', company_key: 'company:globex' }),
  ],
  people: [
    person('Ann', 0, { company: 'Acme', company_key: 'company:acme' }),
    person('Ben', 1, { company: 'Acme', company_key: 'company:acme' }),
  ],
}

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/pins') return json(emptyPins())
      if (url === '/api/statuses') return json({ job: {}, person: {} })
      if (url === '/api/me') return json({ id: 'TEST_USER', display_name: 'Test', created_at: '' })
      if (url === '/api/searches') return json([])
      const entities = url.match(/^\/api\/entities\/(\w+)$/)
      if (entities) return json(ENTITIES[entities[1] as EntityKind])
      return new Response('{}', { status: 404 })
    }),
  )
})

async function renderPage(kind: EntityKind, firstTitle: string) {
  window.location.hash = `#/${kind}`
  const user = userEvent.setup()
  render(<App />)
  const main = screen.getByRole('main')
  await screen.findByRole('heading', { name: new RegExp(firstTitle) })
  return { user, main }
}

const rowOf = (main: HTMLElement, title: string) =>
  within(main)
    .getAllByRole('heading')
    .find((heading) => heading.textContent?.startsWith(title))!
    .closest('li') as HTMLElement

describe('related entities', () => {
  it('lists a company\'s jobs and people beneath its card, and hides empty sections', async () => {
    const { main } = await renderPage('companies', 'Acme')
    await waitFor(() =>
      expect(within(rowOf(main, 'Acme')).getByRole('list', { name: 'Jobs' })).toBeInTheDocument(),
    )
    const acme = rowOf(main, 'Acme')
    expect(within(within(acme).getByRole('list', { name: 'Jobs' })).getByRole('button', { name: 'Engineer' }))
      .toBeInTheDocument()
    const people = within(acme).getByRole('list', { name: 'People to connect with' })
    expect(within(people).getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Ann',
      'Ben',
    ])
    const globex = rowOf(main, 'Globex')
    expect(within(globex).queryByRole('list', { name: 'People to connect with' })).toBeNull()
    const empty = rowOf(main, 'Empty Co')
    expect(within(empty).queryByText('Jobs')).toBeNull()
    expect(within(empty).queryByText('People to connect with')).toBeNull()
  })

  it('lists a job\'s people and jumps to the person card on click', async () => {
    const { user, main } = await renderPage('jobs', 'Engineer')
    const list = await within(rowOf(main, 'Engineer')).findByRole('list', {
      name: 'People to connect with',
    })
    await user.click(within(list).getByRole('button', { name: 'Ben' }))
    await waitFor(() => expect(window.location.hash).toBe('#/people'))
    const ben = await waitFor(() => {
      const row = rowOf(screen.getByRole('main'), 'Ben')
      expect(row).toHaveClass('focused')
      return row
    })
    expect(ben).toHaveAttribute('id', 'entity-person:ben')
  })

  it('lists a person\'s jobs and hides the section when their company has none', async () => {
    const { main } = await renderPage('people', 'Ann')
    const list = await within(rowOf(main, 'Ann')).findByRole('list', { name: 'Jobs at this company' })
    expect(within(list).getByRole('button', { name: 'Engineer' })).toBeInTheDocument()
    expect(within(list).queryByRole('button', { name: 'Designer' })).toBeNull()
  })
})
