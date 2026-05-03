import { Message } from '@/types/types'

export const sendDirectVideoGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  fileIds: string[]
  prompt: string
  duration: number
  aspectRatio: string
  resolution: string
}) => {
  const response = await fetch('/api/direct_video', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: payload.newMessages,
      session_id: payload.sessionId,
      canvas_id: payload.canvasId,
      file_ids: payload.fileIds,
      prompt: payload.prompt,
      duration: payload.duration,
      aspect_ratio: payload.aspectRatio,
      resolution: payload.resolution,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct video request failed: ${response.status}`)
  }
  return await response.json()
}
