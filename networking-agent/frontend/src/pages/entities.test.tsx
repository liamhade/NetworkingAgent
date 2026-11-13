import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EntityKind, PinMap } from '@/api'
import App from '@/App'
import { company, emptyPins, job, person } from '@/test/fixtures'

/**
 * Integration tests for pinning on the Companies / Jobs / People pages. Renders the whole
 * `App` (which owns the pin state and the optimistic toggle) at `#/<kind>`, with `fetch`
 * stubbed to a tiny in-memory backend.
 */

// Server order is most recently seen first.
const ENTITIES = {
  companies: [company('Alpha', 0), company('Bravo', 1), company('Charlie', 2)],
  jobs: [job('Engineer', 0), job('Designer', 1), job('Manager', 2)],
  people: [person('Ann', 0), person('Ben', 1), person('Cat', 2)],
}

interface Backend {
  pins: PinMap
  /** Make the next PUT /api/pins requests fail. */
  failPins: boolean
  pinRequests: unknown[]
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function stubBackend(pins: PinMap = emptyPins()): Backend {
  const backend: Backend = { pins, failPins: false, pinRequests: [] }
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url === '/api/pins' && method === 'PUT') {
      const body = JSON.parse(String(init?.body))
      backend.pinRequests.push(body)
      if (backend.failPins) return json({ detail: 'boom' }, 500)
      backend.pins[body.kind as keyof PinMap][body.key] = body.pinned
      return json({ ...body, updated_at: '2026-01-31T12:00:00Z' })
    }
    if (url === '/api/pins') return json(backend.pins)
    if (url === '/api/statuses') return json({ job: {}, person: {} })
    if (url === '/api/me') return json({ id: 'TEST_USER', display_name: 'Test', created_at: '' })
    if (url === '/api/searches') return json([])
    const entities = url.match(/^\/api\/entities\/(\w+)$/)
    if (entities) return json(ENTITIES[entities[1] as EntityKind])
    return json({ detail: `unexpected ${method} ${url}` }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return backend
}

/** Render the app on an entity page and wait for its cards (and the pins) to load. */
async function renderPage(kind: EntityKind) {
  window.location.hash = `#/${kind}`
  const user = userEvent.setup()
  render(<App />)
  const main = screen.getByRole('main')
  await waitFor(() => expect(within(main).getAllByRole('article')).toHaveLength(3))
  // Let the GET /api/pins load land before interacting.
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pins', expect.anything()))
  return { user, main }
}

/** Card titles in on-screen order. */
const cardTitles = (main: HTMLElement) =>
  within(main)
    .getAllByRole('article')
    .map((card) => within(card).getByRole('heading').textContent)

const pinButton = (main: HTMLElement, name: string) =>
  within(main).getByRole('button', { name: `Pin ${name}` })

async function chooseSort(user: ReturnType<typeof userEvent.setup>, main: HTMLElement, label: string) {
  await user.click(within(main).getByRole('button', { name: /Sort/ }))
  await user.click(await screen.findByRole('option', { name: label }))
}

describe('entity pages: pins', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    window.location.hash = ''
  })

  it('shows saved pins from GET /api/pins', async () => {
    stubBackend({ ...emptyPins(), company: { 'company:bravo': true } })
    const { main } = await renderPage('companies')
    await waitFor(() => expect(pinButton(main, 'Bravo')).toHaveAttribute('aria-pressed', 'true'))
    expect(pinButton(main, 'Alpha')).toHaveAttribute('aria-pressed', 'false')
    expect(pinButton(main, 'Charlie')).toHaveAttribute('aria-pressed', 'false')
  })

  it.each([
    ['companies', 'company', 'Charlie', 'company:charlie'],
    ['jobs', 'job', 'Manager', 'job:manager'],
    ['people', 'person', 'Cat', 'person:cat'],
  ] as const)('%s: clicking a pin toggles it and PUTs /api/pins', async (kind, pinKind, name, key) => {
    const backend = stubBackend()
    const { user, main } = await renderPage(kind)

    await user.click(pinButton(main, name))
    expect(pinButton(main, name)).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(backend.pinRequests).toEqual([{ kind: pinKind, key, pinned: true }]))
    expect(fetch).toHaveBeenCalledWith(
      '/api/pins',
      expect.objectContaining({ method: 'PUT', headers: { 'Content-Type': 'application/json' } }),
    )

    await user.click(pinButton(main, name))
    expect(pinButton(main, name)).toHaveAttribute('aria-pressed', 'false')
    await waitFor(() =>
      expect(backend.pinRequests).toEqual([
        { kind: pinKind, key, pinned: true },
        { kind: pinKind, key, pinned: false },
      ]),
    )
    expect(backend.pins[pinKind][key]).toBe(false)
  })

  it('"Pinned first" puts pinned cards first, keeping recency order within groups', async () => {
    stubBackend({ ...emptyPins(), company: { 'company:charlie': true } })
    const { user, main } = await renderPage('companies')
    await waitFor(() => expect(pinButton(main, 'Charlie')).toHaveAttribute('aria-pressed', 'true'))
    expect(cardTitles(main)).toEqual(['Alpha', 'Bravo', 'Charlie'])

    await chooseSort(user, main, 'Pinned first')
    expect(cardTitles(main)).toEqual(['Charlie', 'Alpha', 'Bravo'])

    // Pinning another card while sorted moves it into the pinned group straight away.
    await user.click(pinButton(main, 'Bravo'))
    expect(cardTitles(main)).toEqual(['Bravo', 'Charlie', 'Alpha'])

    // Back to "Most recent" restores the server order.
    await chooseSort(user, main, 'Most recent')
    expect(cardTitles(main)).toEqual(['Alpha', 'Bravo', 'Charlie'])
  })

  it('"Pinned first" on Jobs', async () => {
    stubBackend({ ...emptyPins(), job: { 'job:manager': true } })
    const jobs = await renderPage('jobs')
    await waitFor(() =>
      expect(pinButton(jobs.main, 'Manager')).toHaveAttribute('aria-pressed', 'true'),
    )
    await chooseSort(jobs.user, jobs.main, 'Pinned first')
    expect(cardTitles(jobs.main)).toEqual(['Manager', 'Engineer', 'Designer'])
  })

  it('"Pinned first" on People', async () => {
    stubBackend({ ...emptyPins(), person: { 'person:ben': true, 'person:cat': true } })
    const { user, main } = await renderPage('people')
    await waitFor(() => expect(pinButton(main, 'Cat')).toHaveAttribute('aria-pressed', 'true'))
    await chooseSort(user, main, 'Pinned first')
    expect(cardTitles(main)).toEqual(['Ben', 'Cat', 'Ann'])
  })

  it('a failed PUT rolls the pin back and shows an error', async () => {
    const backend = stubBackend()
    backend.failPins = true
    const { user, main } = await renderPage('companies')

    await user.click(pinButton(main, 'Alpha'))
    expect(await within(main).findByText('Could not save that pin. Please try again.')).toBeVisible()
    expect(pinButton(main, 'Alpha')).toHaveAttribute('aria-pressed', 'false')
    expect(backend.pinRequests).toEqual([{ kind: 'company', key: 'company:alpha', pinned: true }])

    // The next successful save clears the error.
    backend.failPins = false
    await user.click(pinButton(main, 'Alpha'))
    await waitFor(() =>
      expect(within(main).queryByText('Could not save that pin. Please try again.')).toBeNull(),
    )
    expect(pinButton(main, 'Alpha')).toHaveAttribute('aria-pressed', 'true')
  })

  it('a failed unpin while sorted "Pinned first" puts the card back in the pinned group', async () => {
    const backend = stubBackend({ ...emptyPins(), job: { 'job:designer': true } })
    const { user, main } = await renderPage('jobs')
    await waitFor(() =>
      expect(pinButton(main, 'Designer')).toHaveAttribute('aria-pressed', 'true'),
    )
    await chooseSort(user, main, 'Pinned first')
    expect(cardTitles(main)).toEqual(['Designer', 'Engineer', 'Manager'])

    backend.failPins = true
    await user.click(pinButton(main, 'Designer'))
    await within(main).findByText('Could not save that pin. Please try again.')
    expect(pinButton(main, 'Designer')).toHaveAttribute('aria-pressed', 'true')
    expect(cardTitles(main)).toEqual(['Designer', 'Engineer', 'Manager'])
  })
})
