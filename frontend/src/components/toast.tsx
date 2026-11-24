import { useCallback, useEffect, useRef, useState } from 'react'
import { ToastContext, type ShowToast } from '@/utils/use-toast'

interface ToastState {
  id: number
  message: string
  undo?: () => void
}

const TOAST_MS = 4200

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null)
  const next = useRef(0)
  const show = useCallback<ShowToast>((message, undo) => {
    next.current += 1
    setToast({ id: next.current, message, undo })
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), TOAST_MS)
    return () => window.clearTimeout(timer)
  }, [toast])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={toast ? 'toast show' : 'toast'} role="status" aria-live="polite">
        {toast && (
          <>
            <span>{toast.message}</span>
            {toast.undo && (
              <button
                type="button"
                onClick={() => {
                  toast.undo?.()
                  setToast(null)
                }}
              >
                Undo
              </button>
            )}
          </>
        )}
      </div>
    </ToastContext.Provider>
  )
}
