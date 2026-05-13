import { ToolInfo } from '@/api/model'
import { getCanvas } from '@/api/canvas'
import { uploadImage } from '@/api/upload'
import { TCanvasAddImagesToChatEvent } from '@/lib/event'
import { dataURLToFile } from '@/lib/utils'

const REFERENCE_IMAGE_TOOL_IDS = [
  'generate_image_by_gpt_image_2_edit_apipod',
] as const

export const getPreferredReferenceImageToolId = (
  selectedTools: ToolInfo[]
): string | null => {
  for (const toolId of REFERENCE_IMAGE_TOOL_IDS) {
    const matchedTool = selectedTools.find((tool) => tool.id === toolId)
    if (matchedTool) {
      return matchedTool.id
    }
  }

  const fallbackImageTool = selectedTools.find((tool) => tool.type === 'image')
  return fallbackImageTool?.id || null
}

export const resolveCanvasSelectedImage = async (
  selectedImage: TCanvasAddImagesToChatEvent[number],
  canvasId: string
) => {
  const canvasFileId = String(
    selectedImage.canvasFileId || selectedImage.fileId || ''
  ).trim()

  if (!canvasFileId) {
    throw new Error('未找到画布图片 ID')
  }

  const canvas = await getCanvas(canvasId)
  const canvasFiles = canvas?.data?.files || {}
  const canvasFile = canvasFiles[canvasFileId]
  const canvasDataUrl =
    typeof canvasFile?.dataURL === 'string' ? canvasFile.dataURL : ''
  const inlineDataUrl =
    typeof selectedImage.base64 === 'string' && selectedImage.base64.startsWith('data:')
      ? selectedImage.base64
      : ''

  let referenceImageFileId = canvasFileId
  if (inlineDataUrl) {
    const file = dataURLToFile(inlineDataUrl, `${canvasFileId}.png`)
    const uploaded = await uploadImage(file)
    referenceImageFileId = uploaded.file_id
  }

  return {
    canvasFileId,
    referenceImageFileId,
    imageUrl: inlineDataUrl || canvasDataUrl || `/api/file/${selectedImage.fileId}`,
    width: selectedImage.width,
    height: selectedImage.height,
  }
}

export const resolveCanvasImageByFileId = async (
  canvasFileId: string,
  canvasId: string
) => {
  const normalizedCanvasFileId = String(canvasFileId || '').trim()
  if (!normalizedCanvasFileId) {
    throw new Error('未找到主图文件 ID')
  }

  const canvas = await getCanvas(canvasId)
  const canvasFiles = canvas?.data?.files || {}
  const canvasElements = Array.isArray(canvas?.data?.elements) ? canvas.data.elements : []
  const canvasFile = canvasFiles[normalizedCanvasFileId]
  if (!canvasFile) {
    throw new Error('主图文件不存在于当前画布')
  }

  const matchedElement = canvasElements.find((element: any) => {
    return (
      element &&
      element.type === 'image' &&
      String(element.fileId || '').trim() === normalizedCanvasFileId
    )
  }) as
    | {
        width?: number
        height?: number
      }
    | undefined

  const canvasDataUrl =
    typeof canvasFile?.dataURL === 'string' ? canvasFile.dataURL : ''
  let referenceImageFileId = normalizedCanvasFileId
  if (canvasDataUrl.startsWith('data:')) {
    const file = dataURLToFile(canvasDataUrl, `${normalizedCanvasFileId}.png`)
    const uploaded = await uploadImage(file)
    referenceImageFileId = uploaded.file_id
  }

  return {
    canvasFileId: normalizedCanvasFileId,
    referenceImageFileId,
    imageUrl: canvasDataUrl || `/api/file/${normalizedCanvasFileId}`,
    width: Number(matchedElement?.width || 0),
    height: Number(matchedElement?.height || 0),
  }
}
