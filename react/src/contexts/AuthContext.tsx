import { createContext, useContext, useMemo } from 'react'
import { AuthStatus } from '../api/auth'

interface AuthContextType {
  authStatus: AuthStatus
  isLoading: boolean
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const authStatus = useMemo<AuthStatus>(() => ({
    status: 'logged_out',
    is_logged_in: false,
  }), [])

  const refreshAuth = async () => {
    return
  }

  return (
    <AuthContext.Provider value={{ authStatus, isLoading: false, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
