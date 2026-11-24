import { createContext, useContext } from 'react'

export interface AuthState {
  /** False in development (no Supabase): there is no account to sign out of. */
  enabled: boolean
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState>({ enabled: false, signOut: async () => {} })

export const useAuth = () => useContext(AuthContext)
