import { useCallback, useState } from 'react'

/** `localStorage` key for the Previous Searches sidebar width (px). */
export const SIDEBAR_WIDTH_KEY = 'na-sidebar-width'
export const SIDEBAR_DEFAULT = 272
export const SIDEBAR_MIN = 200
export const SIDEBAR_MAX = 520

export const clampSidebarWidth = (width: number) =>
  Math.round(Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, width)))

function readStored(): number {
  try {
    const stored = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY))
    return stored ? clampSidebarWidth(stored) : SIDEBAR_DEFAULT
  } catch {
    return SIDEBAR_DEFAULT
  }
}

/**
 * The sidebar width: `setWidth` changes it live (e.g. while dragging), `commit` also saves it
 * so it survives a reload.
 */
export function useSidebarWidth() {
  const [width, setRaw] = useState(readStored)
  const setWidth = useCallback((next: number) => setRaw(clampSidebarWidth(next)), [])
  const commit = useCallback((next: number) => {
    const clamped = clampSidebarWidth(next)
    setRaw(clamped)
    try {
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(clamped))
    } catch {
      // Storage unavailable (private mode): the width still applies for this visit.
    }
  }, [])
  return { width, setWidth, commit }
}
