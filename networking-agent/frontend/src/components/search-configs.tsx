import { useState } from 'react'
import type { SearchConfig } from '@/api'
import { Icon } from '@/components/icon'
import { cx } from '@/utils/cx'

/** Mirrors the server's limit on configuration names. */
export const MAX_CONFIG_NAME = 80

interface SearchConfigsProps {
  configs: SearchConfig[]
  loading: boolean
  error: string | null
  /** The configuration last loaded or saved into the form. */
  activeId: string | null
  /** Save the current form as a new configuration; resolves with it. Rejects on failure. */
  onSave: () => Promise<SearchConfig>
  onLoad: (config: SearchConfig) => void
  onRename: (id: string, name: string) => Promise<void>
  /** Overwrite a configuration's parameters with the current form. */
  onOverwrite: (id: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

/** "Saved searches" card in the search page's right rail: saved configurations, in creation order. */
export function SearchConfigs({
  configs,
  loading,
  error,
  activeId,
  onSave,
  onLoad,
  onRename,
  onOverwrite,
  onDelete,
}: SearchConfigsProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  /** Run a server action, surfacing a failure in the card. Resolves undefined on failure. */
  const run = async <T,>(action: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true)
    setActionError(null)
    try {
      return await action()
    } catch (caught) {
      setActionError((caught as Error).message)
      return undefined
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    const created = await run(onSave)
    if (created) setEditingId(created.id) // Name it right away.
  }

  return (
    <section className="card" aria-labelledby="cfgh">
      <h2 id="cfgh">
        <Icon name="save" className="co-c" />
        Saved searches
      </h2>
      <button type="button" className="btn sm wide" onClick={save} disabled={busy}>
        <Icon name="plus" size="sm" />
        Save current setup
      </button>
      {actionError && (
        <p role="alert" className="alert">
          <Icon name="alert" size="sm" />
          {actionError}
        </p>
      )}

      {loading && configs.length === 0 ? (
        <p className="loading">
          <span className="spin" aria-hidden="true" />
          Loading…
        </p>
      ) : error ? (
        <p role="alert" className="alert">
          <Icon name="alert" size="sm" />
          {error}
        </p>
      ) : configs.length === 0 ? (
        <p className="cfg-empty">Save the form as a configuration to reuse it later.</p>
      ) : (
        <ul className="cfg">
          {configs.map((config) => (
            <li key={config.id} className={cx(config.id === activeId && 'on')}>
              {editingId === config.id ? (
                <RenameRow
                  config={config}
                  onCancel={() => setEditingId(null)}
                  onCommit={async (name) => {
                    if (name === config.name) return setEditingId(null)
                    const done = await run(() => onRename(config.id, name).then(() => true))
                    if (done) setEditingId(null)
                  }}
                />
              ) : (
                <ConfigRow
                  config={config}
                  active={config.id === activeId}
                  confirming={confirmingId === config.id}
                  busy={busy}
                  onLoad={() => onLoad(config)}
                  onRename={() => setEditingId(config.id)}
                  onOverwrite={() => run(() => onOverwrite(config.id))}
                  onAskDelete={() => setConfirmingId(config.id)}
                  onCancelDelete={() => setConfirmingId(null)}
                  onDelete={async () => {
                    await run(() => onDelete(config.id))
                    setConfirmingId(null)
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function RenameRow({
  config,
  onCancel,
  onCommit,
}: {
  config: SearchConfig
  onCancel: () => void
  onCommit: (name: string) => void
}) {
  const [name, setName] = useState(config.name)
  const [invalid, setInvalid] = useState(false)

  const commit = () => {
    const trimmed = name.trim()
    if (!trimmed) return setInvalid(true)
    onCommit(trimmed)
  }

  return (
    <div className="rename">
      <input
        type="text"
        aria-label="Configuration name"
        aria-invalid={invalid || undefined}
        autoFocus
        maxLength={MAX_CONFIG_NAME}
        value={name}
        onChange={(event) => {
          setName(event.target.value)
          setInvalid(false)
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault()
            commit()
          } else if (event.key === 'Escape') {
            onCancel()
          }
        }}
      />
      {invalid && <span className="err">Give it a name.</span>}
      <div className="acts">
        <button type="button" className="btn xs pri" onClick={commit}>
          Save name
        </button>
        <button type="button" className="btn xs" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function ConfigRow({
  config,
  active,
  confirming,
  busy,
  onLoad,
  onRename,
  onOverwrite,
  onAskDelete,
  onCancelDelete,
  onDelete,
}: {
  config: SearchConfig
  active: boolean
  confirming: boolean
  busy: boolean
  onLoad: () => void
  onRename: () => void
  onOverwrite: () => void
  onAskDelete: () => void
  onCancelDelete: () => void
  onDelete: () => void
}) {
  const goal = config.params.looking_for.trim()
  return (
    <>
      <div className="nm">
        <span>{config.name}</span>
        {active && <small>Loaded</small>}
      </div>
      <div className="d">{goal || 'No description saved. Load to fill the form.'}</div>
      {confirming ? (
        <div className="confirm">
          Delete this configuration?
          <button type="button" className="btn xs" onClick={onCancelDelete}>
            Keep
          </button>
          <button
            type="button"
            className="btn xs danger"
            aria-label={`Confirm delete ${config.name}`}
            onClick={onDelete}
            disabled={busy}
          >
            Delete
          </button>
        </div>
      ) : (
        <div className="acts">
          <button
            type="button"
            className="btn xs"
            onClick={onLoad}
            aria-current={active ? 'true' : undefined}
            aria-label={`Load ${config.name}`}
          >
            Load
          </button>
          <button
            type="button"
            className="btn xs ghost"
            aria-label={`Rename ${config.name}`}
            title="Rename"
            onClick={onRename}
          >
            <Icon name="edit" size="sm" />
          </button>
          <button
            type="button"
            className="btn xs ghost"
            aria-label={`Overwrite ${config.name} with the current form`}
            title="Overwrite with the current form"
            onClick={onOverwrite}
            disabled={busy}
          >
            <Icon name="save" size="sm" />
          </button>
          <button
            type="button"
            className="btn xs ghost"
            aria-label={`Delete ${config.name}`}
            title="Delete"
            onClick={onAskDelete}
          >
            <Icon name="trash" size="sm" />
          </button>
        </div>
      )}
    </>
  )
}
