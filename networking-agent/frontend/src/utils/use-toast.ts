import { createContext, useContext } from 'react'

export type ShowToast = (message: string, undo?: () => void) => void

export const ToastContext = createContext<ShowToast>(() => {})

/** Short confirmation at the bottom of the screen ("Pinned Acme · Undo"); see `ToastProvider`. */
export const useToast = () => useContext(ToastContext)
