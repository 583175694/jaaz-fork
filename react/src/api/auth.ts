export interface AuthStatus {
  authenticated: boolean
  auth_required: boolean
  status: 'logged_out' | 'logged_in'
  is_logged_in: boolean
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const response = await fetch('/api/auth/status', {
    credentials: 'same-origin',
  })
  if (!response.ok) {
    throw new Error('Failed to check authentication status')
  }
  const data = await response.json()
  const authenticated = Boolean(data.authenticated)
  return {
    authenticated,
    auth_required: Boolean(data.auth_required),
    status: authenticated ? 'logged_in' : 'logged_out',
    is_logged_in: authenticated,
  }
}

export async function loginWithPassword(password: string): Promise<AuthStatus> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password }),
  })
  if (!response.ok) {
    throw new Error('密码不正确')
  }
  const data = await response.json()
  const authenticated = Boolean(data.authenticated)
  return {
    authenticated,
    auth_required: Boolean(data.auth_required),
    status: authenticated ? 'logged_in' : 'logged_out',
    is_logged_in: authenticated,
  }
}

export async function logout(): Promise<{ status: string; message: string }> {
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  return { status: 'success', message: 'Logged out' }
}

export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }

  return fetch(url, {
    ...options,
    credentials: options.credentials || 'same-origin',
    headers,
  })
}
