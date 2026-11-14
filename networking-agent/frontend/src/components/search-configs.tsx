import { useState } from 'react'
import {
  RiAddLine,
  RiArrowDownSLine,
  RiBookmarkLine,
  RiCheckLine,
  RiCloseLine,
  RiDeleteBinLine,
  RiErrorWarningLine,
  RiPencilLine,
  RiSaveLine,
} from '@remixicon/react'
import type { SearchConfig } from '@/api'
import { Button } from '@/components/base/buttons/button'
import { Input } from '@/components/base/input/input'
import { Spinner } from '@/components/base/spinner/spinner'
import { ScrollFade, useScrollFade } from '@/components/foundations/scroll-fade/scroll-fade'
import { cx } from '@/utils/cx'
import { formatRelativeDate, fullDateFormat } from '@/utils/format-date'

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

/**
 * Right side panel of saved search configurations, in creation order. From `lg` it is a
 * sticky column mirroring the history panel; below that it stacks under the form and its
 * list collapses behind a toggle.
 */
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
  const fade = useScrollFade()
  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  /** Run a server action, surfacing a failure in the panel. Resolves undefined on failure. */
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
    if (created) {
      setOpen(true)
      setEditingId(created.id) // "Name it on the side": start renaming right away.
    }
  }

  return (
    <aside
      aria-label="Search configurations"
      className="flex w-full shrink-0 flex-col border-t border-separator-border bg-background-primary-default lg:sticky lg:top-0 lg:h-svh lg:w-72 lg:border-s lg:border-t-0"
    >
      <div className="flex flex-col gap-3 px-4 pt-6 pb-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-caption-1-semibold text-text-tertiary uppercase">
            <RiBookmarkLine aria-hidden className="size-4" />
            Search configurations
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="xs"
            className="lg:hidden"
            aria-expanded={open}
            aria-controls="search-config-list"
            aria-label={open ? 'Hide configurations' : 'Show configurations'}
            leadingIcon={RiArrowDownSLine}
            onClick={() => setOpen((current) => !current)}
          />
        </div>
        <Button
          type="button"
          variant="secondary"
          size="small"
          leadingIcon={RiAddLine}
          onClick={save}
          disabled={busy}
        >
          Save current configuration
        </Button>
        {actionError && (
          <p
            role="alert"
            className="flex items-start gap-1.5 text-body-2-regular text-text-error-primary"
          >
            <RiErrorWarningLine aria-hidden className="mt-0.5 size-4 shrink-0" />
            {actionError}
          </p>
        )}
      </div>

      <div
        id="search-config-list"
        className={cx('relative min-h-0 flex-1', open ? 'block' : 'hidden lg:block')}
      >
        <div
          onScroll={fade.onScroll}
          className="max-h-96 overflow-y-auto px-3 pb-4 lg:h-full lg:max-h-none"
        >
          {loading && configs.length === 0 ? (
            <div className="flex items-center gap-2 px-1 py-2 text-body-2-regular text-text-tertiary">
              <Spinner />
              Loading…
            </div>
          ) : error ? (
            <p
              role="alert"
              className="flex items-start gap-1.5 px-1 py-2 text-body-2-regular text-text-error-primary"
            >
              <RiErrorWarningLine aria-hidden className="mt-0.5 size-4 shrink-0" />
              {error}
            </p>
          ) : configs.length === 0 ? (
            <p className="px-1 py-2 text-body-2-regular text-text-tertiary">
              Save the form as a configuration to reuse it later.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {configs.map((config) => (
                <li key={config.id}>
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
        </div>
        <ScrollFade progress={fade.progress} surfaceClassName="from-background-primary-default" />
      </div>
    </aside>
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
    <div className="flex flex-col gap-2 rounded-2xl border border-border-button-active bg-background-primary-default p-2">
      <Input
        aria-label="Configuration name"
        size="small"
        autoFocus
        maxLength={MAX_CONFIG_NAME}
        value={name}
        onChange={(value) => {
          setName(value)
          setInvalid(false)
        }}
        isInvalid={invalid}
        errorMessage="Give it a name."
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault()
            commit()
          } else if (event.key === 'Escape') {
            onCancel()
          }
        }}
      />
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" size="xs" leadingIcon={RiCloseLine} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="xs"
          leadingIcon={RiCheckLine}
          onClick={commit}
        >
          Save name
        </Button>
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
  const created = new Date(config.created_at)
  return (
    <div
      className={cx(
        'flex flex-col gap-1 rounded-2xl border p-1',
        active
          ? 'border-border-button-active bg-background-primary-active'
          : 'border-border-button-default bg-background-primary-default',
      )}
    >
      <button
        type="button"
        onClick={onLoad}
        aria-current={active ? 'true' : undefined}
        aria-label={`Load ${config.name}`}
        className="flex w-full cursor-pointer flex-col gap-0.5 rounded-xl px-2 py-1.5 text-start transition-colors outline-none hover:bg-background-primary-hover focus-visible:ring-2 focus-visible:ring-border-focus-ring"
      >
        <span className="line-clamp-2 text-body-2-medium break-words text-text-primary">
          {config.name}
        </span>
        <span className="flex items-center gap-1.5 text-caption-1-medium text-text-tertiary">
          <time dateTime={config.created_at} title={fullDateFormat.format(created)}>
            {formatRelativeDate(created)}
          </time>
          {active && <span className="text-text-secondary">· Loaded</span>}
        </span>
      </button>
      {confirming ? (
        <div className="flex items-center justify-between gap-1 px-2 pb-1">
          <span className="text-caption-1-medium text-text-secondary">Delete this one?</span>
          <div className="flex gap-1">
            <Button type="button" variant="ghost" size="xs" onClick={onCancelDelete}>
              Keep
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="xs"
              aria-label={`Confirm delete ${config.name}`}
              onClick={onDelete}
              disabled={busy}
            >
              Delete
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex justify-end gap-0.5 px-1 pb-0.5">
          <Button
            type="button"
            variant="ghost"
            size="xs"
            aria-label={`Rename ${config.name}`}
            leadingIcon={RiPencilLine}
            onClick={onRename}
          />
          <Button
            type="button"
            variant="ghost"
            size="xs"
            aria-label={`Overwrite ${config.name} with the current form`}
            leadingIcon={RiSaveLine}
            onClick={onOverwrite}
            disabled={busy}
          />
          <Button
            type="button"
            variant="ghost"
            size="xs"
            aria-label={`Delete ${config.name}`}
            leadingIcon={RiDeleteBinLine}
            onClick={onAskDelete}
          />
        </div>
      )}
    </div>
  )
}
