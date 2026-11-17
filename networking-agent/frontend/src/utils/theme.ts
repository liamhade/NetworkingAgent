import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

/** `localStorage` key; `index.html` reads it before first paint to avoid a flash. */
export const THEME_KEY = 'na-theme'

export function readTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

/** Light by default; the choice is saved and applied as `data-theme` on `<html>`. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // Private mode: the theme still applies for this visit.
    }
  }, [theme])
  return { theme, setTheme }
}
