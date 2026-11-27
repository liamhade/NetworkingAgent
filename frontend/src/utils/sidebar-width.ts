import { useCallback, useState } from 'react'

/** Width limits (px) and the `localStorage` key a resizable panel saves its width under. */
export interface PanelWidthSpec {
  key: string
  initial: number
  min: number
  max: number
}

/** `localStorage` key for the Previous Searches sidebar width (px). */
export const SIDEBAR_WIDTH_KEY = 'na-sidebar-width'
export const SIDEBAR_MIN = 200
export const SIDEBAR_DEFAULT = SIDEBAR_MIN
export const SIDEBAR_MAX = 520
export const SIDEBAR_SPEC: PanelWidthSpec = {
  key: SIDEBAR_WIDTH_KEY,
  initial: SIDEBAR_DEFAULT,
  min: SIDEBAR_MIN,
  max: SIDEBAR_MAX,
}

const clamp = (spec: PanelWidthSpec, width: number) =>
  Math.round(Math.min(spec.max, Math.max(spec.min, width)))

export const clampSidebarWidth = (width: number) => clamp(SIDEBAR_SPEC, width)

function readStored(spec: PanelWidthSpec): number {
  try {
    const stored = Number(localStorage.getItem(spec.key))
    return stored ? clamp(spec, stored) : spec.initial
  } catch {
    return spec.initial
  }
}

/**
 * A resizable panel's width: `setWidth` changes it live (e.g. while dragging), `commit` also
 * saves it so it survives a reload.
 */
export function usePanelWidth(spec: PanelWidthSpec) {
  const [width, setRaw] = useState(() => readStored(spec))
  const setWidth = useCallback((next: number) => setRaw(clamp(spec, next)), [spec])
  const commit = useCallback(
    (next: number) => {
      const clamped = clamp(spec, next)
      setRaw(clamped)
      try {
        localStorage.setItem(spec.key, String(clamped))
      } catch {
        // Storage unavailable (private mode): the width still applies for this visit.
      }
    },
    [spec],
  )
  return { width, setWidth, commit }
}

/** The Previous Searches sidebar width. */
export const useSidebarWidth = () => usePanelWidth(SIDEBAR_SPEC)
