import { useId, useState } from 'react'
import { signIn, signUp } from '@/api'

type Mode = 'sign-in' | 'sign-up'

const MIN_PASSWORD = 8

/** Email + password sign-in, and invite-code sign-up. */
export function SignInPage({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<Mode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ids = { email: useId(), password: useId(), invite: useId(), hint: useId() }

  const signingUp = mode === 'sign-up'
  const canSubmit =
    !busy &&
    email.trim() !== '' &&
    password !== '' &&
    (!signingUp || (inviteCode.trim() !== '' && password.length >= MIN_PASSWORD))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError('')
    try {
      if (signingUp) await signUp(email.trim(), password, inviteCode.trim())
      else await signIn(email.trim(), password)
      onSignedIn()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  function switchTo(next: Mode) {
    setMode(next)
    setError('')
  }

  return (
    <main className="auth-page">
      <form className="card auth-card" onSubmit={submit} noValidate>
        <h1>Networking Agent</h1>
        <p className="hint">
          {signingUp
            ? 'Create your account with the invite code you were given.'
            : 'Sign in to find companies, jobs and people to connect with.'}
        </p>

        <div className="field">
          <label htmlFor={ids.email}>Email</label>
          <input
            id={ids.email}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor={ids.password}>Password</label>
          <input
            id={ids.password}
            type="password"
            autoComplete={signingUp ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby={signingUp ? ids.hint : undefined}
            required
          />
          {signingUp && (
            <div className="hint" id={ids.hint}>
              At least {MIN_PASSWORD} characters.
            </div>
          )}
        </div>
        {signingUp && (
          <div className="field">
            <label htmlFor={ids.invite}>Invite code</label>
            <input
              id={ids.invite}
              type="text"
              autoComplete="off"
              spellCheck={false}
              placeholder="ABCD-EFGH"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              required
            />
          </div>
        )}

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        <button className="btn pri auth-submit" type="submit" disabled={!canSubmit}>
          {busy ? 'Please wait…' : signingUp ? 'Create account' : 'Sign in'}
        </button>

        <p className="auth-switch">
          {signingUp ? 'Already have an account?' : 'Have an invite code?'}{' '}
          <button
            type="button"
            className="link-btn"
            onClick={() => switchTo(signingUp ? 'sign-in' : 'sign-up')}
          >
            {signingUp ? 'Sign in' : 'Create an account'}
          </button>
        </p>
      </form>
    </main>
  )
}
