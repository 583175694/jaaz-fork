import { GenerationJob, Message } from '@/types/types'
import { Model } from '@/types/types'
import { ImageModelOption } from '@/lib/imageModels'
import { getClientId } from '@/lib/client'

export const previewDirectStoryboardPrompt = async (payload: {
  textModel?: Model
  prompt: string
  shotCount: number
  aspectRatio: string
}) => {
  const response = await fetch('/api/direct_storyboard/prompt_preview', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text_model: payload.textModel,
      prompt: payload.prompt,
      shot_count: payload.shotCount,
      aspect_ratio: payload.aspectRatio,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct storyboard prompt preview failed: ${response.status}`)
  }
  const json = await response.json()
  return json?.result
}

export const sendDirectStoryboardGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  mainImageFileId: string
  referenceImageFileId?: string
  prompt: string
  shotCount: number
  aspectRatio: string
  imageToolId?: string
  imageModel?: ImageModelOption
  skipPromptConfirmation?: boolean
}): Promise<{ status: string; job_id?: string; job?: GenerationJob }> => {
  const response = await fetch('/api/direct_storyboard', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: getClientId(),
      messages: payload.newMessages,
      session_id: payload.sessionId,
      canvas_id: payload.canvasId,
      main_image_file_id: payload.mainImageFileId,
      reference_image_file_id: payload.referenceImageFileId,
      prompt: payload.prompt,
      shot_count: payload.shotCount,
      aspect_ratio: payload.aspectRatio,
      image_tool_id: payload.imageToolId,
      image_model: payload.imageModel,
      skip_prompt_confirmation: payload.skipPromptConfirmation,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct storyboard request failed: ${response.status}`)
  }
  return await response.json()
}

export const sendDirectMultiviewGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  sourceFileId: string
  referenceImageFileId?: string
  prompt: string
  presetName: string
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
  aspectRatio: string
  imageModel?: ImageModelOption
  previewOnly?: boolean
  replaceSource?: boolean
  imageToolId?: string
}): Promise<{ status: string; job_id?: string; job?: GenerationJob }> => {
  const response = await fetch('/api/direct_multiview', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: getClientId(),
      messages: payload.newMessages,
      session_id: payload.sessionId,
      canvas_id: payload.canvasId,
      source_file_id: payload.sourceFileId,
      reference_image_file_id: payload.referenceImageFileId,
      prompt: payload.prompt,
      preset_name: payload.presetName,
      azimuth: payload.azimuth,
      elevation: payload.elevation,
      framing: payload.framing,
      aspect_ratio: payload.aspectRatio,
      image_model: payload.imageModel,
      preview_only: payload.previewOnly,
      replace_source: payload.replaceSource,
      image_tool_id: payload.imageToolId,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct multiview request failed: ${response.status}`)
  }
  return await response.json()
}

export const sendDirectStoryboardRefine = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  sourceFileId: string
  referenceImageFileId?: string
  prompt: string
  aspectRatio: string
  mode?: 'append' | 'replace'
  imageToolId?: string
  imageModel?: ImageModelOption
}): Promise<{ status: string; job_id?: string; job?: GenerationJob }> => {
  const response = await fetch('/api/storyboard/refine', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: getClientId(),
      messages: payload.newMessages,
      session_id: payload.sessionId,
      canvas_id: payload.canvasId,
      source_file_id: payload.sourceFileId,
      reference_image_file_id: payload.referenceImageFileId,
      prompt: payload.prompt,
      aspect_ratio: payload.aspectRatio,
      mode: payload.mode,
      image_tool_id: payload.imageToolId,
      image_model: payload.imageModel,
    }),
  })
  if (!response.ok) {
    throw new Error(`Storyboard refine request failed: ${response.status}`)
  }
  return await response.json()
}

export const markStoryboardPrimaryVariant = async (payload: {
  canvasId: string
  fileId: string
}) => {
  const response = await fetch('/api/storyboard/mark_primary', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      canvas_id: payload.canvasId,
      file_id: payload.fileId,
      client_id: getClientId(),
    }),
  })
  if (!response.ok) {
    throw new Error(`Mark primary storyboard variant failed: ${response.status}`)
  }
  return await response.json()
}
