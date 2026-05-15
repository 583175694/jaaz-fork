import { GenerationJob, Message, Model } from '@/types/types'

export const previewDirectVideoPrompt = async (payload: {
  canvasId: string
  textModel?: Model
  fileIds: string[]
  prompt: string
  duration: number
  aspectRatio: string
  resolution: string
  videoModel?: 'veo3-1-quality' | 'seedance-2.0-fast-i2v'
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
      video_model: payload.videoModel,
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
  videoModel?: 'veo3-1-quality' | 'seedance-2.0-fast-i2v'
  selectionMode?: 'start_end_frames'
  startFrameFileId?: string
  endFrameFileId?: string
  skipPromptConfirmation?: boolean
  skipPromptCompilation?: boolean
}): Promise<{ status: 'accepted'; job_id: string; job: GenerationJob }> => {
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
      video_model: payload.videoModel,
      selection_mode: payload.selectionMode,
      start_frame_file_id: payload.startFrameFileId,
      end_frame_file_id: payload.endFrameFileId,
      skip_prompt_confirmation: payload.skipPromptConfirmation,
      skip_prompt_compilation: payload.skipPromptCompilation,
    }),
  })
  if (!response.ok) {
    throw new Error(`Direct video request failed: ${response.status}`)
  }
  return await response.json()
}

export const getGenerationJob = async (
  jobId: string
): Promise<{ job: GenerationJob | null }> => {
  const response = await fetch(`/api/jobs/${jobId}`)
  if (!response.ok) {
    throw new Error(`Get generation job failed: ${response.status}`)
  }
  return await response.json()
}

export const listCanvasGenerationJobs = async (
  canvasId: string,
  params?: {
    type?: string
    status?: string
    limit?: number
  }
): Promise<{ jobs: GenerationJob[] }> => {
  const search = new URLSearchParams()
  if (params?.type) {
    search.set('type', params.type)
  }
  if (params?.status) {
    search.set('status', params.status)
  }
  if (typeof params?.limit === 'number') {
    search.set('limit', String(params.limit))
  }
  const query = search.toString()
  const response = await fetch(
    `/api/canvases/${canvasId}/jobs${query ? `?${query}` : ''}`
  )
  if (!response.ok) {
    throw new Error(`List canvas generation jobs failed: ${response.status}`)
  }
  return await response.json()
}
