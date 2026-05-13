import { createContext, useContext, useEffect, useState } from 'react'
import { AuthStatus, getAuthStatus, loginWithPassword, logout } from '../api/auth'

interface AuthContextType {
  authStatus: AuthStatus
  isLoading: boolean
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus>({
    authenticated: false,
    auth_required: true,
    status: 'logged_out',
    is_logged_in: false,
  })
  const [isLoading, setIsLoading] = useState(true)

  const refreshAuth = async () => {
    setIsLoading(true)
    try {
      setAuthStatus(await getAuthStatus())
    } catch (error) {
      console.error('Failed to refresh auth status:', error)
      setAuthStatus({
        authenticated: false,
        auth_required: true,
        status: 'logged_out',
        is_logged_in: false,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (password: string) => {
    setAuthStatus(await loginWithPassword(password))
  }

  const handleLogout = async () => {
    await logout()
    await refreshAuth()
  }

  useEffect(() => {
    void refreshAuth()
  }, [])

  return (
    <AuthContext.Provider
      value={{ authStatus, isLoading, login, logout: handleLogout, refreshAuth }}
    >
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
