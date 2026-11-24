import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UNAUTHORIZED_EVENT } from '@/api'
import { AuthGate } from '@/components/auth-gate'
import { SignInPage } from '@/pages/sign-in'

const USER = { id: 'u1', display_name: 'a@x.com', created_at: '2026-11-24T00:00:00Z' }
const OWNER = 'owner@example.com'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('SignInPage', () => {
  it('signs in with email and password', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(USER))
    vi.stubGlobal('fetch', fetchMock)
    const onSignedIn = vi.fn()
    render(<SignInPage onSignedIn={onSignedIn} requestEmail={OWNER} />)

    await userEvent.type(screen.getByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/login')
    expect(JSON.parse(init.body)).toEqual({ email: 'a@x.com', password: 'secret' })
    expect(onSignedIn).toHaveBeenCalled()
  })

  it('requests access, then asks for the confirmation email', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ access: 'pending' }, 202))
    vi.stubGlobal('fetch', fetchMock)
    const onSignedIn = vi.fn()
    render(<SignInPage onSignedIn={onSignedIn} requestEmail={OWNER} />)

    await userEvent.click(screen.getByRole('button', { name: 'Request access' }))
    await userEvent.type(screen.getByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    const submit = screen.getByRole('button', { name: 'Request access' })
    expect(submit).toBeDisabled() // password under 8 characters

    await userEvent.type(screen.getByLabelText('Password'), 'enough')
    await userEvent.click(submit)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/signup')
    expect(JSON.parse(init.body)).toEqual({ email: 'a@x.com', password: 'shortenough' })

    expect(await screen.findByRole('heading', { name: 'Confirm your email' })).toBeInTheDocument()
    const mail = screen.getByRole('link', { name: 'Send the request email' })
    const href = mail.getAttribute('href') ?? ''
    expect(href.startsWith(`mailto:${OWNER}?subject=`)).toBe(true)
    expect(decodeURIComponent(href)).toContain('Please approve a@x.com')
    expect(onSignedIn).not.toHaveBeenCalled()
  })

  it('sends a pending account to the email step, and shows a refusal', async () => {
    const waiting = { detail: 'Your access request is waiting for approval.', access: 'pending' }
    const refused = { detail: "Your access request wasn't approved.", access: 'denied' }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(refused, 403))
      .mockResolvedValueOnce(json(waiting, 403))
    vi.stubGlobal('fetch', fetchMock)
    render(<SignInPage onSignedIn={vi.fn()} requestEmail="" />)

    await userEvent.type(screen.getByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent("wasn't approved")

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Confirm your email' })).toBeInTheDocument()
    // No owner inbox configured: say who to ask instead of offering a broken link.
    expect(screen.getByText(/Ask the person who runs this app/)).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})

describe('AuthGate', () => {
  it('shows the app without accounts (development)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ enabled: false })))
    render(<AuthGate>app content</AuthGate>)
    expect(await screen.findByText('app content')).toBeInTheDocument()
  })

  it('asks signed-out users to sign in, and returns there on any 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ enabled: true }))
      .mockResolvedValueOnce(json(USER)) // /api/me: signed in
    vi.stubGlobal('fetch', fetchMock)
    render(<AuthGate>app content</AuthGate>)
    expect(await screen.findByText('app content')).toBeInTheDocument()

    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText('app content')).not.toBeInTheDocument()
  })
})
