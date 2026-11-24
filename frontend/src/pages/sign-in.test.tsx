import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { UNAUTHORIZED_EVENT } from '@/api'
import { AuthGate } from '@/components/auth-gate'
import { SignInPage } from '@/pages/sign-in'

const USER = { id: 'u1', display_name: 'a@x.com', created_at: '2026-11-24T00:00:00Z' }

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
    render(<SignInPage onSignedIn={onSignedIn} />)

    await userEvent.type(screen.getByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/login')
    expect(JSON.parse(init.body)).toEqual({ email: 'a@x.com', password: 'secret' })
    expect(onSignedIn).toHaveBeenCalled()
  })

  it('signs up with an invite code and shows server errors', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ detail: "That invite code isn't valid." }, 400))
      .mockResolvedValueOnce(json(USER))
    vi.stubGlobal('fetch', fetchMock)
    const onSignedIn = vi.fn()
    render(<SignInPage onSignedIn={onSignedIn} />)

    await userEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    await userEvent.type(screen.getByLabelText('Email'), 'a@x.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.type(screen.getByLabelText('Invite code'), 'abcd-efgh')
    const submit = screen.getByRole('button', { name: 'Create account' })
    expect(submit).toBeDisabled() // password under 8 characters

    await userEvent.type(screen.getByLabelText('Password'), 'enough')
    await userEvent.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent("That invite code isn't valid.")
    expect(onSignedIn).not.toHaveBeenCalled()

    await userEvent.click(submit)
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/auth/signup')
    expect(JSON.parse(init.body)).toEqual({
      email: 'a@x.com',
      password: 'shortenough',
      invite_code: 'abcd-efgh',
    })
    expect(onSignedIn).toHaveBeenCalled()
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
