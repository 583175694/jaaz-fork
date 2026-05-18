import {
  sendDirectMultiviewGenerate,
  sendDirectStoryboardRefine,
} from '@/api/storyboard'
import { getPendingWorkflowConfirmations } from '@/api/canvas'
import {
  getPreferredReferenceImageToolId,
  resolveCanvasSelectedImage,
} from '@/components/chat/canvasGenerationUtils'
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasGenerateMultiviewEvent } from '@/lib/event'
import { GenerationJob, Message } from '@/types/types'
import { useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'

type ChatCanvasMultiviewGeneratorProps = {
  sessionId: string
  canvasId: string
  messages: Message[]
  setMessages: (messages: Message[]) => void
  onQueueJobAccepted: (job: GenerationJob) => void
  scrollToBottom: () => void
}

const ChatCanvasMultiviewGenerator: React.FC<
  ChatCanvasMultiviewGeneratorProps
> = ({
  sessionId,
  canvasId,
  messages,
  setMessages,
  onQueueJobAccepted,
  scrollToBottom,
}) => {
  const inFlightRef = useRef(false)
  const { selectedTools } = useConfigs()

  const handleGenerateMultiview = useCallback(
    async (data: TCanvasGenerateMultiviewEvent) => {
      if (inFlightRef.current) {
        return
      }

      inFlightRef.current = true

      try {
        const imageToolId = getPreferredReferenceImageToolId(selectedTools)
        if (!imageToolId) {
          throw new Error('当前未启用支持参考图的图片模型')
        }

        const resolvedImage = await resolveCanvasSelectedImage(
          data.selectedImage,
          canvasId
        )

        const message: Message = {
          role: 'user',
          content: [
            {
              type: 'text',
              text:
                '请基于当前分镜图生成新的多视角候选，并保持主体身份、服装、产品形态、场景气质与灯光连续。新图必须仍属于同一镜头家族，但机位或景别要明显不同。\n' +
                `<task>multiview-storyboard-variant</task>\n` +
                `<source_image canvas_file_id="${resolvedImage.canvasFileId}" reference_file_id="${resolvedImage.referenceImageFileId}" />\n` +
                `<preset_name>${data.presetName || 'custom'}</preset_name>\n` +
                `<azimuth>${data.azimuth}</azimuth>\n` +
                `<elevation>${data.elevation}</elevation>\n` +
                `<framing>${data.framing}</framing>\n` +
                `<aspect_ratio>${data.aspectRatio}</aspect_ratio>\n` +
                `<preview_only>${data.previewOnly ? 'true' : 'false'}</preview_only>\n` +
                `<replace_source>${data.replaceSource ? 'true' : 'false'}</replace_source>\n` +
                `<prompt>${data.prompt || '保持当前分镜连续性的多视角候选'}</prompt>`,
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

        if (data.mode === 'refinement') {
          const response = await sendDirectStoryboardRefine({
            sessionId,
            canvasId,
            newMessages,
            sourceFileId: resolvedImage.canvasFileId,
            referenceImageFileId: resolvedImage.referenceImageFileId,
            prompt: data.prompt,
            aspectRatio: data.aspectRatio,
            mode: data.replaceSource ? 'replace' : 'append',
            imageToolId,
            imageModel: data.imageModel,
          })
          if (response.job?.deduplicated) {
            setMessages(messages)
            toast.info('相同镜头编辑任务已在队列中', {
              description: '不会重复创建任务，已复用当前排队项。',
            })
          }
          if (response?.job) {
            onQueueJobAccepted(response.job)
          }
        } else {
          const response = await sendDirectMultiviewGenerate({
            sessionId,
            canvasId,
            newMessages,
            sourceFileId: resolvedImage.canvasFileId,
            referenceImageFileId: resolvedImage.referenceImageFileId,
            prompt: data.prompt,
            presetName: data.presetName,
            azimuth: data.azimuth,
            elevation: data.elevation,
            framing: data.framing,
            aspectRatio: data.aspectRatio,
            imageModel: data.imageModel,
            previewOnly: data.previewOnly,
            replaceSource: data.replaceSource,
            imageToolId,
          })
          if (response.job?.deduplicated) {
            setMessages(messages)
            toast.info('相同多视角任务已在队列中', {
              description: '不会重复创建任务，已复用当前排队项。',
            })
          }
          if (response?.job) {
            onQueueJobAccepted(response.job)
          }
        }

        // Multiview/refine requests rely on realtime confirmation pushes.
        // If the websocket event arrives before the chat panel re-subscribes
        // after a canvas refresh, pull pending confirmations once so the card
        // still appears reliably.
        setTimeout(() => {
          void getPendingWorkflowConfirmations(sessionId)
        }, 200)

        window.dispatchEvent(
          new CustomEvent('app:refresh-canvas', {
            detail: {
              canvasId,
              reason: data.replaceSource
                ? 'direct-multiview-replace-complete'
                : 'direct-multiview-complete',
            },
          })
        )
      } catch (error) {
        console.error('Failed to send multiview generation message:', error)
        toast.error('发起多视角候选失败', {
          description: String(error),
        })
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
      onQueueJobAccepted,
    ]
  )

  useEffect(() => {
    eventBus.on('Canvas::GenerateMultiview', handleGenerateMultiview)

    return () => {
      eventBus.off('Canvas::GenerateMultiview', handleGenerateMultiview)
    }
  }, [handleGenerateMultiview])

  return null
}

export default ChatCanvasMultiviewGenerator
