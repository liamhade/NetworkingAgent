import { useCallback, useEffect, useState } from 'react'
import { getAuthConfig, signOut, UNAUTHORIZED_EVENT } from '@/api'
import { SignInPage } from '@/pages/sign-in'
import { AuthContext } from '@/utils/auth-context'

type Phase = 'checking' | 'signed-in' | 'signed-out' | 'offline'

/**
 * Shows the app only to a signed-in user. Asks `/api/auth/config` and `/api/me` once, then
 * goes back to the sign-in page whenever any API call answers 401. Children remount on every
 * sign-in, so one user's data never lingers for the next.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<Phase>('checking')
  const [enabled, setEnabled] = useState(false)
  const [session, setSession] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    getAuthConfig(controller.signal)
      .then(async (config) => {
        setEnabled(config.enabled)
        if (!config.enabled) return setPhase('signed-in')
        const response = await fetch('/api/me', { signal: controller.signal })
        setPhase(response.ok ? 'signed-in' : response.status === 401 ? 'signed-out' : 'offline')
      })
      .catch(() => !controller.signal.aborted && setPhase('offline'))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const onUnauthorized = () => setPhase((p) => (p === 'signed-in' ? 'signed-out' : p))
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const handleSignOut = useCallback(async () => {
    try {
      await signOut()
    } finally {
      setPhase('signed-out')
    }
  }, [])

  if (phase === 'checking') return null
  if (phase === 'offline') {
    return (
      <main className="auth-page">
        <div className="card auth-card">
          <h1>Can&rsquo;t reach the server</h1>
          <p className="hint">Check your connection and reload the page.</p>
        </div>
      </main>
    )
  }
  if (phase === 'signed-out') {
    return (
      <SignInPage
        onSignedIn={() => {
          setSession((n) => n + 1)
          setPhase('signed-in')
        }}
      />
    )
  }
  return (
    <AuthContext.Provider value={{ enabled, signOut: handleSignOut }}>
      <div key={session} style={{ display: 'contents' }}>
        {children}
      </div>
    </AuthContext.Provider>
  )
}
