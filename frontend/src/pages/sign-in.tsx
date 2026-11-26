import { useId, useState } from 'react'
import { AccessError, signIn, signUp } from '@/api'
import { ACCESS_REQUEST_SUBJECT, accessRequestMailto } from '@/utils/access-request'

type Mode = 'sign-in' | 'request' | 'awaiting'

const MIN_PASSWORD = 8

interface SignInPageProps {
  onSignedIn: () => void
  /** Where access requests are emailed (`ACCESS_REQUEST_EMAIL`); empty if unset. */
  requestEmail: string
  /** `LOCAL_DEV_MODE`: any email and password (even empty) sign in as TEST_USER. */
  localDev?: boolean
}

/** Email + password sign-in, and access requests the owner approves by email. */
export function SignInPage({ onSignedIn, requestEmail, localDev = false }: SignInPageProps) {
  const [mode, setMode] = useState<Mode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ids = { email: useId(), password: useId(), hint: useId() }

  const requesting = mode === 'request'
  const canSubmit =
    !busy &&
    (localDev ||
      (email.trim() !== '' &&
        password !== '' &&
        (!requesting || password.length >= MIN_PASSWORD)))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError('')
    try {
      if (requesting) {
        const result = await signUp(email.trim(), password)
        if (result === 'pending') return setMode('awaiting')
      } else {
        await signIn(email.trim(), password)
      }
      onSignedIn()
    } catch (err) {
      if (err instanceof AccessError && err.access === 'pending') return setMode('awaiting')
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  function switchTo(next: Mode) {
    setMode(next)
    setError('')
    setPassword('')
  }

  if (mode === 'awaiting') {
    const address = email.trim()
    return (
      <main className="auth-page">
        <div className="card auth-card">
          <h1>Confirm your email</h1>
          {requestEmail ? (
            <>
              <p className="hint">
                One last step: send a short email from <strong>{address}</strong>. Sending it from
                that address is how we confirm it&rsquo;s yours. You can sign in once your request
                is approved.
              </p>
              <a className="btn pri auth-submit" href={accessRequestMailto(requestEmail, address)}>
                Send the request email
              </a>
              <p className="hint">
                If no email opens, write to <strong>{requestEmail}</strong> from {address} with the
                subject &ldquo;{ACCESS_REQUEST_SUBJECT}&rdquo;.
              </p>
            </>
          ) : (
            <p className="hint">
              Ask the person who runs this app to approve <strong>{address}</strong>. You can sign
              in once they have.
            </p>
          )}
          <p className="auth-switch">
            Approved already?{' '}
            <button type="button" className="link-btn" onClick={() => switchTo('sign-in')}>
              Sign in
            </button>
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="auth-page">
      <form className="card auth-card" onSubmit={submit} noValidate>
        <h1>Networking Agent</h1>
        <p className="hint">
          {requesting
            ? 'Choose a password and request access. You’ll then email us from this address to confirm it.'
            : 'Sign in to find companies, jobs and people to connect with.'}
        </p>
        {localDev && (
          <p className="dev-note" role="note">
            <b>Local dev mode.</b> Any email and password (or none) sign you in as TEST_USER.
          </p>
        )}

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
            autoComplete={requesting ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby={requesting ? ids.hint : undefined}
            required
          />
          {requesting && (
            <div className="hint" id={ids.hint}>
              At least {MIN_PASSWORD} characters.
            </div>
          )}
        </div>

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        <button className="btn pri auth-submit" type="submit" disabled={!canSubmit}>
          {busy ? 'Please wait…' : requesting ? 'Request access' : 'Sign in'}
        </button>

        {!localDev && (
          <p className="auth-switch">
            {requesting ? 'Already approved?' : 'New here?'}{' '}
            <button
              type="button"
              className="link-btn"
              onClick={() => switchTo(requesting ? 'sign-in' : 'request')}
            >
              {requesting ? 'Sign in' : 'Request access'}
            </button>
          </p>
        )}
      </form>
    </main>
  )
}
