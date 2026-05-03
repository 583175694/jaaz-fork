import { Message, Model } from '@/types/types'
import { ToolInfo } from './model'

export const sendMagicGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  systemPrompt: string | null
  width: number
  height: number
  relationHint: 'single' | 'multi'
  selectedImageCount: number
  selectedImageBase64s: string[]
  selectedImagePositions: Array<{ fileId: string; x: number; y: number }>
}) => {
  const response = await fetch(`/api/magic`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      system_prompt: payload.systemPrompt,
      width: payload.width,
      height: payload.height,
      relation_hint: payload.relationHint,
      selected_image_count: payload.selectedImageCount,
      selected_image_base64s: payload.selectedImageBase64s,
      selected_image_positions: payload.selectedImagePositions,
    }),
  })
  const data = await response.json()
  return data as Message[]
}

export const cancelMagicGenerate = async (sessionId: string) => {
    const response = await fetch(`/api/magic/cancel/${sessionId}`, {
        method: 'POST',
    })
    return await response.json()
}
