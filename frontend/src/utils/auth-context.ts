import { createContext, useContext } from 'react'

export interface AuthState {
  /** False in development (no Supabase): there is no account to sign out of. */
  enabled: boolean
  /** `LOCAL_DEV_MODE`: signed in as TEST_USER without a password (nothing to change). */
  localDev: boolean
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthState>({
  enabled: false,
  localDev: false,
  signOut: async () => {},
})

export const useAuth = () => useContext(AuthContext)
