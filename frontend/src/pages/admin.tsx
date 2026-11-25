import { useEffect, useState } from 'react'
import {
  addToWhitelist,
  getAdminOverview,
  removeFromWhitelist,
  resetUserPassword,
  type AdminOverview,
  type AdminUser,
  type WhitelistStatus,
} from '@/api'
import { Icon } from '@/components/icon'
import { PageHeader } from '@/components/page-header'
import { ErrorBanner } from '@/pages/results'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'
import { withRetry } from '@/utils/retry'

const STATUS_LABEL: Record<WhitelistStatus, string> = {
  approved: 'Whitelisted',
  pending: 'Requested',
  denied: 'Removed',
}
const STATUS_CLASS: Record<WhitelistStatus, string> = {
  approved: 'con',
  pending: 'pin',
  denied: 'bad',
}

const usd = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})
const count = new Intl.NumberFormat()
const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

function When({ iso }: { iso: string | null }) {
  if (!iso) return <span className="muted">—</span>
  const date = new Date(iso)
  return (
    <time dateTime={iso} title={fullDateFormat.format(date)}>
      {formatRelativeDate(date)}
    </time>
  )
}

/**
 * The owner's page: who may use the app (the whitelist) and what each user's LLM calls cost.
 * Adding approves an email (a pending request, or in advance); removing blocks it at once.
 */
export function AdminPage() {
  const [data, setData] = useState<AdminOverview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [adding, setAdding] = useState(false)
  /** The email whose action is in flight. */
  const [busy, setBusy] = useState<string | null>(null)
  /** The row waiting for "Confirm remove" / "Confirm reset". */
  const [confirming, setConfirming] = useState<{ email: string; action: 'remove' | 'reset' } | null>(
    null,
  )
  /** The last temporary password set, shown once to pass on. */
  const [temporary, setTemporary] = useState<{ email: string; password: string } | null>(null)
  const [copied, setCopied] = useState(false)

  const reload = (signal?: AbortSignal) =>
    withRetry(getAdminOverview, signal)
      .then((overview) => {
        setData(overview)
        setLoadError(null)
      })
      .catch((caught: Error) => {
        if (!signal?.aborted) setLoadError(caught.message || 'Could not load users.')
      })

  useEffect(() => {
    const controller = new AbortController()
    reload(controller.signal)
    return () => controller.abort()
  }, [])

  const run = async (target: string, action: () => Promise<unknown>) => {
    setActionError(null)
    setBusy(target)
    try {
      await action()
      await reload()
    } catch (caught) {
      setActionError((caught as Error).message)
    } finally {
      setBusy(null)
      setConfirming(null)
    }
  }

  const add = async (event: React.FormEvent) => {
    event.preventDefault()
    const value = email.trim()
    if (!value) return
    setAdding(true)
    await run(value.toLowerCase(), () => addToWhitelist(value))
    setAdding(false)
    setEmail('')
  }

  const users = data?.users ?? []
  const whitelisted = users.filter((u) => u.status === 'approved').length
  const pending = users.filter((u) => u.status === 'pending').length

  const actions = (user: AdminUser) => {
    if (user.is_owner) return <span className="muted">Owner</span>
    if (!user.email.includes('@')) return <span className="muted">No email</span>
    const disabled = busy !== null
    if (confirming?.email === user.email) {
      const removing = confirming.action === 'remove'
      return (
        <>
          <button
            type="button"
            className="btn xs danger"
            disabled={disabled}
            onClick={() =>
              run(user.email, async () => {
                if (removing) return removeFromWhitelist(user.email)
                setCopied(false)
                setTemporary(await resetUserPassword(user.email))
              })
            }
          >
            {removing ? 'Confirm remove' : 'Confirm reset'}
          </button>
          <button
            type="button"
            className="btn xs ghost"
            disabled={disabled}
            onClick={() => setConfirming(null)}
          >
            Cancel
          </button>
        </>
      )
    }
    return (
      <>
        {user.status !== 'approved' && (
          <button
            type="button"
            className="btn xs"
            disabled={disabled}
            onClick={() => run(user.email, () => addToWhitelist(user.email))}
          >
            <Icon name="check" />
            {user.status === 'pending' ? 'Approve' : user.status === 'denied' ? 'Restore' : 'Add'}
          </button>
        )}
        {user.status === 'approved' && (
          <button
            type="button"
            className="btn xs danger"
            disabled={disabled}
            onClick={() => setConfirming({ email: user.email, action: 'remove' })}
          >
            Remove
          </button>
        )}
        {user.status === 'approved' && (
          <button
            type="button"
            className="btn xs ghost"
            disabled={disabled}
            title="Set a new temporary password to send them"
            onClick={() => setConfirming({ email: user.email, action: 'reset' })}
          >
            Reset password
          </button>
        )}
        {user.status === 'pending' && (
          <button
            type="button"
            className="btn xs ghost"
            disabled={disabled}
            onClick={() => run(user.email, () => removeFromWhitelist(user.email))}
          >
            Deny
          </button>
        )}
      </>
    )
  }

  return (
    <div className="wrap">
      <PageHeader
        title="Admin"
        subtitle="Only whitelisted emails can use the app. Removing an email signs that person out at once."
        actions={
          data && (
            <div className="stats">
              <span className="stat per">
                <span className="n num">{whitelisted}</span>
                <span className="l">whitelisted</span>
              </span>
              {pending > 0 && (
                <span className="stat pin">
                  <span className="n num">{pending}</span>
                  <span className="l">waiting</span>
                </span>
              )}
              <span className="stat co">
                <span className="n num">{usd.format(data.totals.cost_usd)}</span>
                <span className="l">LLM spend</span>
              </span>
            </div>
          )
        }
      />

      <form className="card admin-add" onSubmit={add}>
        <label htmlFor="whitelist-email" className="lbl">
          Add to whitelist
        </label>
        <div className="admin-add-row">
          <input
            id="whitelist-email"
            type="email"
            required
            placeholder="name@example.com"
            autoComplete="off"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" className="btn pri" disabled={adding || !email.trim()}>
            <Icon name="plus" />
            Add
          </button>
        </div>
        <p className="hint">
          They can sign in once they have an account. If they haven&rsquo;t requested access
          yet, their request is approved the moment they make it.
        </p>
      </form>

      {temporary && (
        <div className="card admin-temp" role="status">
          <Icon name="check" />
          <div>
            <p>
              New temporary password for <b>{temporary.email}</b>. Send it to them; it
              isn&rsquo;t shown again. They can change it from the top bar after signing in.
            </p>
            <div className="admin-temp-row">
              <code>{temporary.password}</code>
              <button
                type="button"
                className="btn xs"
                onClick={() =>
                  navigator.clipboard
                    ?.writeText(temporary.password)
                    .then(() => setCopied(true))
                    .catch(() => {})
                }
              >
                <Icon name="copy" />
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                type="button"
                className="btn xs ghost"
                aria-label="Dismiss"
                onClick={() => setTemporary(null)}
              >
                <Icon name="x" />
              </button>
            </div>
          </div>
        </div>
      )}
      {actionError && <ErrorBanner message={actionError} />}
      {loadError && <ErrorBanner message={loadError} />}

      {!data && !loadError && (
        <p className="loading">
          <span className="spin" aria-hidden="true" />
          Loading users…
        </p>
      )}

      {data && (
        <div className="card admin-table-wrap">
          <table className="admin-table">
            <caption className="sr">Users, their access and LLM usage</caption>
            <thead>
              <tr>
                <th scope="col">Email</th>
                <th scope="col">Access</th>
                <th scope="col" className="r">
                  LLM calls
                </th>
                <th scope="col" className="r">
                  Tokens
                </th>
                <th scope="col" className="r">
                  Cost
                </th>
                <th scope="col">Last used</th>
                <th scope="col">Requested</th>
                <th scope="col">
                  <span className="sr">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr>
                  <td colSpan={8} className="muted">
                    No users yet.
                  </td>
                </tr>
              )}
              {users.map((user) => (
                <tr key={user.email} aria-busy={busy === user.email || undefined}>
                  <th scope="row">
                    <span className="admin-email">
                      {user.email}
                      {user.is_owner && <span className="pill neu tight">you</span>}
                    </span>
                  </th>
                  <td>
                    {user.status ? (
                      <span className={`pill tight ${STATUS_CLASS[user.status]}`}>
                        {STATUS_LABEL[user.status]}
                      </span>
                    ) : (
                      <span className="muted">Never asked</span>
                    )}
                  </td>
                  <td className="r num">{count.format(user.usage.calls)}</td>
                  <td className="r num" title={count.format(user.usage.total_tokens)}>
                    {compact.format(user.usage.total_tokens)}
                  </td>
                  <td className="r num">{usd.format(user.usage.cost_usd)}</td>
                  <td>
                    <When iso={user.usage.last_used_at || null} />
                  </td>
                  <td>
                    <When iso={user.requested_at} />
                  </td>
                  <td>
                    <div className="admin-acts">{actions(user)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
            {users.length > 0 && (
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td />
                  <td className="r num">{count.format(data.totals.calls)}</td>
                  <td className="r num" title={count.format(data.totals.total_tokens)}>
                    {compact.format(data.totals.total_tokens)}
                  </td>
                  <td className="r num">{usd.format(data.totals.cost_usd)}</td>
                  <td colSpan={3} />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  )
}
