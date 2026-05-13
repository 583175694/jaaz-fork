export interface AuthStatus {
  status: 'logged_out' | 'pending' | 'logged_in'
  is_logged_in: boolean
  user_info?: UserInfo
  tokenExpired?: boolean
}

export interface UserInfo {
  id: string
  username: string
  email: string
  image_url?: string
  provider?: string
  created_at?: string
  updated_at?: string
}

export interface DeviceAuthResponse {
  status: string
  code: string
  expires_at: string
  message: string
}

export interface DeviceAuthPollResponse {
  status: 'pending' | 'authorized' | 'expired' | 'error'
  message?: string
  token?: string
  user_info?: UserInfo
}

export interface ApiResponse {
  status: string
  message: string
}

export async function startDeviceAuth(): Promise<DeviceAuthResponse> {
  throw new Error('Authentication is disabled in this build')
}

export async function pollDeviceAuth(
  _deviceCode: string
): Promise<DeviceAuthPollResponse> {
  return {
    status: 'error',
    message: 'Authentication is disabled in this build',
  }
}

export async function getAuthStatus(): Promise<AuthStatus> {
  return {
    status: 'logged_out',
    is_logged_in: false,
  }
}

export async function logout(): Promise<{ status: string; message: string }> {
  return {
    status: 'success',
    message: 'Authentication is disabled in this build',
  }
}

export async function getUserProfile(): Promise<UserInfo> {
  throw new Error('Authentication is disabled in this build')
}

export function saveAuthData(_token: string, _userInfo: UserInfo) {
  return
}

export function getAccessToken(): string | null {
  return null
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
    headers,
  })
}

export async function refreshToken(_currentToken: string) {
  throw new Error('Authentication is disabled in this build')
}
