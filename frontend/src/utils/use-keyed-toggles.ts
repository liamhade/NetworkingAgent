import { useCallback, useRef, useState } from 'react'

/** `{kind: {entityKey: on}}`, as returned by `/api/statuses` and `/api/pins`. */
export type ToggleMap<K extends string> = Record<K, Record<string, boolean>>

/**
 * Per-entity on/off marks (APPLIED / CONNECTED statuses, pins) with optimistic updates:
 * `toggle` applies the change at once, saves it, and rolls back with `failMessage` if the
 * save fails. A per-entry version counter makes sure a stale failed request never rolls
 * back a newer change.
 */
export function useKeyedToggles<K extends string>(
  empty: ToggleMap<K>,
  save: (kind: K, key: string, on: boolean) => Promise<void>,
  failMessage: string,
) {
  const [map, setMap] = useState<ToggleMap<K>>(empty)
  const [error, setError] = useState<string | null>(null)
  const versions = useRef(new Map<string, number>())

  /** Replace the whole map with a freshly loaded one. */
  const load = useCallback(
    (loaded: Partial<ToggleMap<K>>) => {
      setMap({ ...empty, ...loaded })
      setError(null)
    },
    [empty],
  )

  const toggle = async (kind: K, key: string, on: boolean) => {
    const previous = map[kind][key] ?? false
    const versionKey = `${kind}:${key}`
    const version = (versions.current.get(versionKey) ?? 0) + 1
    versions.current.set(versionKey, version)
    const apply = (value: boolean) =>
      setMap((current) => ({ ...current, [kind]: { ...current[kind], [key]: value } }))

    apply(on)
    try {
      await save(kind, key, on)
      if (versions.current.get(versionKey) === version) setError(null)
    } catch (caught) {
      console.error(caught)
      if (versions.current.get(versionKey) !== version) return
      apply(previous)
      setError(failMessage)
    }
  }

  return { map, error, setError, load, toggle }
}
