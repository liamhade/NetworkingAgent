import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AdminOverview, AdminUser } from '@/api'
import App from '@/App'

/** The owner's Admin tab: rendered through `App` at `#/admin`, `fetch` stubbed. */

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const usage = (calls = 0, cost = 0) => ({
  calls,
  total_tokens: calls * 1000,
  cost_usd: cost,
  last_used_at: calls ? '2026-11-20T10:00:00Z' : '',
})

const row = (email: string, status: AdminUser['status'], extra: Partial<AdminUser> = {}) => ({
  email,
  status,
  is_owner: false,
  user_id: '',
  requested_at: null,
  decided_at: null,
  joined_at: null,
  usage: usage(),
  ...extra,
})

function stubBackend(isAdmin: boolean) {
  const users: AdminUser[] = [
    row('boss@x.com', 'approved', { is_owner: true, usage: usage(3, 0.3) }),
    row('ann@x.com', 'pending'),
    row('ben@x.com', 'approved', { usage: usage(2, 1.25) }),
  ]
  const requests: string[] = []
  const overview = (): AdminOverview => ({
    owner_email: 'boss@x.com',
    users,
    totals: usage(5, 1.55),
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      if (url.startsWith('/api/admin')) requests.push(`${method} ${url}`)
      if (url === '/api/me')
        return json({ id: 'u1', display_name: 'boss@x.com', created_at: '', is_admin: isAdmin })
      if (url === '/api/admin/users') return json(overview())
      if (url === '/api/admin/whitelist' && method === 'PUT') {
        const { email } = JSON.parse(String(init?.body))
        const found = users.find((u) => u.email === email)
        if (found) found.status = 'approved'
        else users.push(row(email, 'approved'))
        return json({ email, status: 'approved' })
      }
      const reset = url.match(/^\/api\/admin\/users\/(.+)\/reset-password$/)
      if (reset && method === 'POST')
        return json({ email: decodeURIComponent(reset[1]), password: 'Temp-Pass-123' })
      const removed = url.match(/^\/api\/admin\/whitelist\/(.+)$/)
      if (removed && method === 'DELETE') {
        const email = decodeURIComponent(removed[1])
        users.find((u) => u.email === email)!.status = 'denied'
        return json({ email, status: 'denied' })
      }
      if (url === '/api/statuses') return json({ job: {}, person: {} })
      if (url === '/api/pins') return json({ company: {}, job: {}, person: {} })
      if (url === '/api/searches' || url === '/api/search/configs' || url === '/api/search/boards')
        return json([])
      return json(null)
    }),
  )
  return requests
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

describe('Admin tab', () => {
  it('is hidden from everyone but the owner', async () => {
    const requests = stubBackend(false)
    window.location.hash = '#/admin'
    render(<App />)
    await screen.findByRole('link', { name: 'People' })
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Admin' })).toBeNull()
    expect(requests).toEqual([])
  })

  /** Render the Admin tab and wait for its table. */
  async function openAdmin() {
    const requests = stubBackend(true)
    window.location.hash = '#/admin'
    render(<App />)
    const table = await screen.findByRole('table')
    const rowOf = (email: RegExp) => screen.getByRole('row', { name: email })
    return { requests, table, rowOf, user: userEvent.setup() }
  }

  it('lists users with their usage', async () => {
    const { table } = await openAdmin()
    expect(screen.getByRole('link', { name: 'Admin' })).toBeTruthy()
    const ben = within(table).getByRole('row', { name: /ben@x\.com/ })
    expect(within(ben).getByText('$1.25')).toBeTruthy()
    expect(within(table).getByRole('row', { name: /boss@x\.com/ }).textContent).toContain('Owner')
  })

  it('approves a pending request', async () => {
    const { requests, rowOf, user } = await openAdmin()
    await user.click(within(rowOf(/ann@x\.com/)).getByRole('button', { name: /Approve/ }))
    await waitFor(() => expect(within(rowOf(/ann@x\.com/)).getByText('Whitelisted')))
    expect(requests).toContain('PUT /api/admin/whitelist')
  })

  it('removes a whitelisted email after confirming', async () => {
    const { requests, rowOf, user } = await openAdmin()
    await user.click(within(rowOf(/ben@x\.com/)).getByRole('button', { name: 'Remove' }))
    await user.click(screen.getByRole('button', { name: 'Confirm remove' }))
    await waitFor(() => expect(within(rowOf(/ben@x\.com/)).getByText('Removed')))
    expect(requests).toContain('DELETE /api/admin/whitelist/ben%40x.com')
  })

  it('adds a new email', async () => {
    const { user } = await openAdmin()
    await user.type(screen.getByLabelText('Add to whitelist'), 'new@x.com')
    await user.click(screen.getByRole('button', { name: 'Add' }))
    expect(await screen.findByRole('row', { name: /new@x\.com/ })).toBeTruthy()
  })

  it('resets a password and shows the temporary one once', async () => {
    const { requests, rowOf, user } = await openAdmin()
    await user.click(within(rowOf(/ben@x\.com/)).getByRole('button', { name: 'Reset password' }))
    await user.click(screen.getByRole('button', { name: 'Confirm reset' }))
    expect(await screen.findByText('Temp-Pass-123')).toBeTruthy()
    expect(requests).toContain('POST /api/admin/users/ben%40x.com/reset-password')
    expect(screen.getByText(/New temporary password for/).textContent).toContain('ben@x.com')
    await user.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByText('Temp-Pass-123')).toBeNull()
  })
})
