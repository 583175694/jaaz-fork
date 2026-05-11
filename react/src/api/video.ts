import { Message, Model } from '@/types/types'

export const previewDirectVideoPrompt = async (payload: {
  canvasId: string
  textModel?: Model
  fileIds: string[]
  prompt: string
  duration: number
  aspectRatio: string
  resolution: string
  selectionMode?: 'start_end_frames'
  startFrameFileId?: string
  endFrameFileId?: string
}) => {
  const response = await fetch('/api/direct_video/prompt_preview', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      canvas_id: payload.canvasId,
      text_model: payload.textModel,
      file_ids: payload.fileIds,
      prompt: payload.prompt,
      duration: payload.duration,
      aspect_ratio: payload.aspectRatio,
      resolution: payload.resolution,
      selection_mode: payload.selectionMode,
      start_frame_file_id: payload.startFrameFileId,
      end_frame_file_id: payload.endFrameFileId,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct video prompt preview failed: ${response.status}`)
  }
  const json = await response.json()
  return json?.result
}

export const sendDirectVideoGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  textModel?: Model
  fileIds: string[]
  prompt: string
  duration: number
  aspectRatio: string
  resolution: string
  selectionMode?: 'start_end_frames'
  startFrameFileId?: string
  endFrameFileId?: string
  skipPromptConfirmation?: boolean
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
      text_model: payload.textModel,
      file_ids: payload.fileIds,
      prompt: payload.prompt,
      duration: payload.duration,
      aspect_ratio: payload.aspectRatio,
      resolution: payload.resolution,
      selection_mode: payload.selectionMode,
      start_frame_file_id: payload.startFrameFileId,
      end_frame_file_id: payload.endFrameFileId,
      skip_prompt_confirmation: payload.skipPromptConfirmation,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct video request failed: ${response.status}`)
  }
  return await response.json()
}
