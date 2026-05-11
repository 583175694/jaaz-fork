import { sendDirectStoryboardGenerate } from '@/api/storyboard'
import {
  resolveCanvasImageByFileId,
  getPreferredReferenceImageToolId,
  resolveCanvasSelectedImage,
} from '@/components/chat/canvasGenerationUtils'
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasGenerateStoryboardEvent } from '@/lib/event'
import { Message, PendingType } from '@/types/types'
import { useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'

type ChatCanvasStoryboardGeneratorProps = {
  sessionId: string
  canvasId: string
  messages: Message[]
  setMessages: (messages: Message[]) => void
  setPending: (pending: PendingType) => void
  scrollToBottom: () => void
}

const ChatCanvasStoryboardGenerator: React.FC<
  ChatCanvasStoryboardGeneratorProps
> = ({
  sessionId,
  canvasId,
  messages,
  setMessages,
  setPending,
  scrollToBottom,
}) => {
  const inFlightRef = useRef(false)
  const { selectedTools } = useConfigs()

  const handleGenerateStoryboard = useCallback(
    async (data: TCanvasGenerateStoryboardEvent) => {
      if (inFlightRef.current) {
        toast.info('分镜生成正在进行中，请等待当前任务完成')
        return
      }

      inFlightRef.current = true
      setPending('text')

      try {
        const imageToolId = getPreferredReferenceImageToolId(selectedTools)
        if (!imageToolId) {
          throw new Error('当前未启用支持参考图的图片模型')
        }

        const selectedCanvasFileId = String(
          data.selectedImage.canvasFileId || data.selectedImage.fileId || ''
        ).trim()

        let resolvedImage
        if (data.mainImageFileId && data.mainImageFileId !== selectedCanvasFileId) {
          try {
            resolvedImage = await resolveCanvasImageByFileId(
              data.mainImageFileId,
              canvasId
            )
          } catch (error) {
            console.warn('Failed to resolve stored main image, fallback to selected image', {
              canvasId,
              mainImageFileId: data.mainImageFileId,
              error,
            })
            resolvedImage = await resolveCanvasSelectedImage(
              data.selectedImage,
              canvasId
            )
          }
        } else {
          resolvedImage = await resolveCanvasSelectedImage(
            data.selectedImage,
            canvasId
          )
        }

        const message: Message = {
          role: 'user',
          content: [
            {
              type: 'text',
              text:
                '请基于当前选中的主图扩展电影感分镜，并保持主体身份、服装、产品形态、场景氛围与灯光连续。首轮每镜先生成 1 个主镜头，要求镜头之间有明确的景别、机位或视线差异。\n' +
                `<task>main-image-to-storyboard</task>\n` +
                `<main_image canvas_file_id="${resolvedImage.canvasFileId}" reference_file_id="${resolvedImage.referenceImageFileId}" />\n` +
                `<shot_count>${data.shotCount}</shot_count>\n` +
                `<variant_count_per_shot>${data.variantCountPerShot}</variant_count_per_shot>\n` +
                `<aspect_ratio>${data.aspectRatio}</aspect_ratio>\n` +
                `<prompt>${data.prompt || '基于主图自动扩展分镜'}</prompt>`,
            },
            {
              type: 'image_url',
              image_url: {
                url: resolvedImage.imageUrl,
              },
            },
          ],
        }

        const newMessages = [...messages, message]
        setMessages(newMessages)
        scrollToBottom()

        await sendDirectStoryboardGenerate({
          sessionId,
          canvasId,
          newMessages,
          mainImageFileId: resolvedImage.canvasFileId,
          referenceImageFileId: resolvedImage.referenceImageFileId,
          prompt: data.prompt,
          shotCount: data.shotCount,
          variantCountPerShot: data.variantCountPerShot,
          aspectRatio: data.aspectRatio,
          imageToolId,
        })

        window.dispatchEvent(
          new CustomEvent('jaaz:refresh-canvas', {
            detail: {
              canvasId,
              reason: 'direct-storyboard-complete',
            },
          })
        )
      } catch (error) {
        console.error('Failed to send storyboard generation message:', error)
        toast.error('发起分镜生成失败', {
          description: String(error),
        })
        setPending(false)
      } finally {
        inFlightRef.current = false
      }
    },
    [
      canvasId,
      messages,
      scrollToBottom,
      selectedTools,
      sessionId,
      setMessages,
      setPending,
    ]
  )

  useEffect(() => {
    eventBus.on('Canvas::GenerateStoryboard', handleGenerateStoryboard)

    return () => {
      eventBus.off('Canvas::GenerateStoryboard', handleGenerateStoryboard)
    }
  }, [handleGenerateStoryboard])

  return null
}

export default ChatCanvasStoryboardGenerator
