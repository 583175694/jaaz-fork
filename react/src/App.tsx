import UpdateNotificationDialog from '@/components/common/UpdateNotificationDialog'
import { ThemeProvider } from '@/components/theme/ThemeProvider'
import { ConfigsProvider } from '@/contexts/configs'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { SocketProvider } from '@/contexts/socket'
import PasswordGate from '@/components/auth/PasswordGate'
import { useTheme } from '@/hooks/use-theme'
import { getOrCreateClientId } from '@/lib/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister'
import { openDB } from 'idb'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { routeTree } from './route-tree.gen'

import '@/assets/style/App.css'
import '@/i18n'

if (typeof window !== 'undefined') {
  getOrCreateClientId()
}

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

// 创建 IndexedDB 连接
const getDB = () =>
  openDB('react-query-db', 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('cache')) {
        db.createObjectStore('cache')
      }
    },
  })

// 创建 IndexedDB 持久化器
const persister = createAsyncStoragePersister({
  storage: {
    getItem: async (key: string) => {
      const db = await getDB()
      return (await db.get('cache', key)) || null
    },
    setItem: async (key: string, value: unknown) => {
      const db = await getDB()
      await db.put('cache', value, key)
    },
    removeItem: async (key: string) => {
      const db = await getDB()
      await db.delete('cache', key)
    },
  },
  key: 'react-query-cache',
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
    },
  },
})

function App() {
  const { theme } = useTheme()

  return (
    <ThemeProvider defaultTheme={theme} storageKey="vite-ui-theme">
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{ persister }}
      >
        <AuthProvider>
          <AuthenticatedApp />
        </AuthProvider>
      </PersistQueryClientProvider>
      <Toaster position="bottom-center" richColors />
    </ThemeProvider>
  )
}

function AuthenticatedApp() {
  const { authStatus, isLoading } = useAuth()

  if (isLoading) {
    return <div className="min-h-screen bg-background" />
  }

  if (authStatus.auth_required && !authStatus.authenticated) {
    return <PasswordGate />
  }

  return (
    <SocketProvider>
      <ConfigsProvider>
        <div className="app-container">
          <RouterProvider router={router} />
          <UpdateNotificationDialog />
        </div>
      </ConfigsProvider>
    </SocketProvider>
  )
}

export default App
