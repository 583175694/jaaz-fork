import { SocketProvider } from '@/contexts/socket'
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { PostHogProvider } from 'posthog-js/react'
import '@/assets/style/index.css'

const posthogKey = String(import.meta.env.VITE_PUBLIC_POSTHOG_KEY || '').trim()
const options = {
  api_host: import.meta.env.VITE_PUBLIC_POSTHOG_HOST,
}

const rootElement = document.getElementById('root')!
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  const app = (
    <StrictMode>
      <SocketProvider>
        <App />
      </SocketProvider>
    </StrictMode>
  )

  root.render(
    posthogKey ? (
      <PostHogProvider apiKey={posthogKey} options={options}>
        {app}
      </PostHogProvider>
    ) : (
      app
    )
  )
}
