import {
  CanvasData,
  ContinuityAsset,
  Message,
  Session,
  StoryboardPlanAsset,
  VideoBriefAsset,
} from '@/types/types'
import { ToolInfo } from '@/api/model'
import { getClientId } from '@/lib/client'

export type ListCanvasesResponse = {
  id: string
  name: string
  description?: string
  thumbnail?: string
  created_at: string
}

export async function listCanvases(): Promise<ListCanvasesResponse[]> {
  const response = await fetch(`/api/canvas/list?client_id=${encodeURIComponent(getClientId())}`)
  return await response.json()
}

export async function createCanvas(data: {
  name: string
  canvas_id: string
  messages: Message[]
  session_id: string
  text_model: {
    provider: string
    model: string
    url: string
  }
  tool_list: ToolInfo[]

  system_prompt: string
}): Promise<{ id: string }> {
  const response = await fetch('/api/canvas/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...data,
      client_id: getClientId(),
    }),
  })
  return await response.json()
}

export async function getCanvas(
  id: string
): Promise<{ data: CanvasData; name: string; sessions: Session[] }> {
  const response = await fetch(
    `/api/canvas/${id}?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function getCurrentContinuity(
  canvasId: string
): Promise<{ item: ContinuityAsset | null }> {
  const response = await fetch(
    `/api/continuity/${canvasId}/current?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function getCurrentMainImage(
  canvasId: string
): Promise<{ file_id: string }> {
  const response = await fetch(
    `/api/main_image/${canvasId}/current?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function setCurrentMainImage(
  canvasId: string,
  fileId: string
): Promise<{ status: string; file_id: string }> {
  const response = await fetch(`/api/main_image/${canvasId}/current`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_id: fileId,
      client_id: getClientId(),
    }),
  })
  return await response.json()
}

export async function getStoryboardPlan(
  canvasId: string,
  storyboardId: string
): Promise<{ item: StoryboardPlanAsset | null }> {
  const response = await fetch(
    `/api/storyboard/${canvasId}/${storyboardId}?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function getCurrentStoryboardPlan(
  canvasId: string
): Promise<{ item: StoryboardPlanAsset | null }> {
  const response = await fetch(
    `/api/storyboard/${canvasId}/current?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function getCurrentVideoBrief(
  canvasId: string
): Promise<{ item: VideoBriefAsset | null }> {
  const response = await fetch(
    `/api/video/brief/${canvasId}/current?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export type PendingWorkflowItem = {
  tool_call_id: string
  session_id: string
  tool_name: string
  kind?: string
  target_id?: string
  arguments: Record<string, unknown>
  created_at: string
}

export async function getPendingWorkflowConfirmations(
  sessionId: string
): Promise<{ items: PendingWorkflowItem[] }> {
  const response = await fetch(
    `/api/workflow/${sessionId}/pending?client_id=${encodeURIComponent(getClientId())}`
  )
  return await response.json()
}

export async function saveCanvas(
  id: string,
  payload: {
    data: CanvasData
    thumbnail: string
  }
): Promise<void> {
  const response = await fetch(`/api/canvas/${id}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...payload,
      client_id: getClientId(),
    }),
  })
  return await response.json()
}

export async function renameCanvas(id: string, name: string): Promise<void> {
  const response = await fetch(`/api/canvas/${id}/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      client_id: getClientId(),
    }),
  })
  return await response.json()
}

export async function deleteCanvas(id: string): Promise<void> {
  const response = await fetch(
    `/api/canvas/${id}/delete?client_id=${encodeURIComponent(getClientId())}`,
    {
      method: 'DELETE',
    }
  )
  return await response.json()
}
