import { nanoid } from 'nanoid'

export const CLIENT_ID_STORAGE_KEY = 'jaaz_client_id'

export function getOrCreateClientId(): string {
  if (typeof window === 'undefined') {
    return `cli_${nanoid()}`
  }

  const existing = localStorage.getItem(CLIENT_ID_STORAGE_KEY) || ''
  if (existing.trim()) {
    return existing.trim()
  }

  const nextValue = `cli_${nanoid()}`
  localStorage.setItem(CLIENT_ID_STORAGE_KEY, nextValue)
  return nextValue
}

export function getClientId(): string {
  return getOrCreateClientId()
}
