import { sendDirectVideoGenerate } from '@/api/video'
import { getCanvas } from '@/api/canvas'
import { uploadImage } from '@/api/upload'
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasGenerateVideoEvent } from '@/lib/event'
import { dataURLToFile } from '@/lib/utils'
import { GenerationJob, Message } from '@/types/types'
import { useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'

const MAX_REFERENCE_IMAGES = 2

type ChatCanvasVideoGeneratorProps = {
  sessionId: string
  canvasId: string
  messages: Message[]
  setMessages: (messages: Message[]) => void
  onQueueJobAccepted: (job: GenerationJob) => void
  scrollToBottom: () => void
}

const ChatCanvasVideoGenerator: React.FC<ChatCanvasVideoGeneratorProps> = ({
  sessionId,
  canvasId,
  messages,
  setMessages,
  onQueueJobAccepted,
  scrollToBottom,
}) => {
  const { textModel } = useConfigs()
  const inFlightRef = useRef(false)

  const handleGenerateVideo = useCallback(
    async (data: TCanvasGenerateVideoEvent) => {
      if (inFlightRef.current) {
        return
      }

      const selectedImages = data.selectedImages.slice(0, MAX_REFERENCE_IMAGES)
      if (selectedImages.length === 0) {
        return
      }

      inFlightRef.current = true

      try {
        const needsCanvasFileLookup = selectedImages.some((selectedImage) => {
          const fileId = String(selectedImage.fileId || '')
          return (
            fileId.startsWith('im_') ||
            fileId.startsWith('vi_') ||
            !fileId.includes('.')
          )
        })

        const canvasFiles = needsCanvasFileLookup
          ? ((await getCanvas(canvasId))?.data?.files || {})
          : {}

        const resolvedImages = await Promise.all(
          selectedImages.map(async (selectedImage) => {
            const hasInlineDataUrl =
              typeof selectedImage.base64 === 'string' &&
              selectedImage.base64.startsWith('data:')

            let fileId = selectedImage.fileId
            let imageUrl = `/api/file/${fileId}`

            if (hasInlineDataUrl && selectedImage.base64) {
              const file = dataURLToFile(selectedImage.base64, selectedImage.fileId)
              const uploaded = await uploadImage(file)
              fileId = uploaded.file_id
              imageUrl = `/api/file/${fileId}`
            } else {
              const canvasFile = canvasFiles[fileId]
              const canvasDataUrl =
                typeof canvasFile?.dataURL === 'string' ? canvasFile.dataURL : ''
              if (canvasDataUrl) {
                imageUrl = canvasDataUrl
              }
            }

            return {
              ...selectedImage,
              fileId,
              imageUrl,
            }
          })
        )

        const duration = data.duration
        const startFrame = resolvedImages[0]
        const endFrame = resolvedImages.length > 1 ? resolvedImages[1] : resolvedImages[0]

        const message: Message = {
          role: 'user',
          content: [
            {
              type: 'text',
              text: data.finalPrompt,
            },
            ...resolvedImages.map((image) => ({
              type: 'image_url' as const,
              image_url: {
                url: image.imageUrl,
              },
            })),
          ],
        }

        const newMessages = [...messages, message]
        setMessages(newMessages)
        scrollToBottom()

        const response = await sendDirectVideoGenerate({
          sessionId,
          canvasId,
          newMessages: newMessages,
          textModel,
          fileIds: resolvedImages.map((image) => image.fileId),
          prompt: data.finalPrompt,
          duration,
          aspectRatio: data.aspectRatio,
          resolution: data.resolution,
          videoModel: data.videoModel,
          selectionMode: 'start_end_frames',
          startFrameFileId: startFrame.fileId,
          endFrameFileId: endFrame.fileId,
          skipPromptConfirmation: true,
          skipPromptCompilation: true,
        })
        if (response.job?.deduplicated) {
          setMessages(messages)
          toast.info('相同视频任务已在队列中', {
            description: '不会重复创建任务，已为你定位到现有队列项。',
          })
        }
        if (response.job) {
          onQueueJobAccepted(response.job)
        }
        if (!response.job?.deduplicated) {
          toast.success('视频任务已提交', {
            description:
              response.job.status === 'queued'
                ? '任务已进入队列'
                : '任务已开始生成',
          })
        }
      } catch (error) {
        console.error('Failed to send canvas video generation message:', error)
        toast.error('发起视频生成失败', {
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
      sessionId,
      setMessages,
      onQueueJobAccepted,
      textModel,
    ]
  )

  useEffect(() => {
    eventBus.on('Canvas::GenerateVideo', handleGenerateVideo)

    return () => {
      eventBus.off('Canvas::GenerateVideo', handleGenerateVideo)
    }
  }, [handleGenerateVideo])

  return null
}

export default ChatCanvasVideoGenerator
