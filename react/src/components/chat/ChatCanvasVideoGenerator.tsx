import { sendDirectVideoGenerate } from '@/api/video'
import { getCanvas } from '@/api/canvas'
import { uploadImage } from '@/api/upload'
import { eventBus, TCanvasGenerateVideoEvent } from '@/lib/event'
import { dataURLToFile } from '@/lib/utils'
import { Message, PendingType } from '@/types/types'
import { useCallback, useEffect } from 'react'
import { toast } from 'sonner'

const MAX_REFERENCE_IMAGES = 2

type ChatCanvasVideoGeneratorProps = {
  sessionId: string
  canvasId: string
  messages: Message[]
  setMessages: (messages: Message[]) => void
  setPending: (pending: PendingType) => void
  scrollToBottom: () => void
}

const ChatCanvasVideoGenerator: React.FC<ChatCanvasVideoGeneratorProps> = ({
  sessionId,
  canvasId,
  messages,
  setMessages,
  setPending,
  scrollToBottom,
}) => {
  const handleGenerateVideo = useCallback(
    async (data: TCanvasGenerateVideoEvent) => {
      const selectedImages = data.selectedImages.slice(0, MAX_REFERENCE_IMAGES)
      if (selectedImages.length === 0) {
        return
      }

      setPending('text')

      try {
        const resolvedImages = await Promise.all(
          selectedImages.map(async (selectedImage) => {
            const hasInlineDataUrl =
              typeof selectedImage.base64 === 'string' &&
              selectedImage.base64.startsWith('data:')

            let fileId = selectedImage.fileId
            if (hasInlineDataUrl && selectedImage.base64) {
              const file = dataURLToFile(selectedImage.base64, selectedImage.fileId)
              const uploaded = await uploadImage(file)
              fileId = uploaded.file_id
            }

            return {
              ...selectedImage,
              fileId,
              imageUrl: `/api/file/${fileId}`,
            }
          })
        )

        const duration = data.duration
        const inputImagesXml = resolvedImages
          .map(
            (image, index) =>
              `<image index="${index + 1}" file_id="${image.fileId}" width="${image.width}" height="${image.height}" />`
          )
          .join('\n')

        const message: Message = {
          role: 'user',
          content: [
            {
              type: 'text',
              text:
                `${data.prompt}\n\n` +
                `<duration>${duration}</duration>\n` +
                `<aspect_ratio>${data.aspectRatio}</aspect_ratio>\n` +
                `<input_images count="${resolvedImages.length}">\n` +
                `${inputImagesXml}\n` +
                `</input_images>`,
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

        await sendDirectVideoGenerate({
          sessionId,
          canvasId,
          newMessages: newMessages,
          fileIds: resolvedImages.map((image) => image.fileId),
          prompt: data.prompt,
          duration,
          aspectRatio: data.aspectRatio,
          resolution: data.resolution,
        })

        const startedAt = Date.now()
        let foundVideo = false
        while (Date.now() - startedAt < 15000) {
          try {
            const latestCanvas = await getCanvas(canvasId)
            const files = latestCanvas?.data?.files || {}
            const hasNewVideo = Object.values(files).some((file: any) =>
              String(file?.mimeType || '').startsWith('video/')
            )
            if (hasNewVideo) {
              console.log('🎥 Video detected via canvas poll fallback', {
                canvasId,
              })
              window.dispatchEvent(
                new CustomEvent('jaaz:refresh-canvas', {
                  detail: {
                    canvasId,
                    reason: 'direct-video-fallback',
                  },
                })
              )
              foundVideo = true
              break
            }
          } catch (pollError) {
            console.warn('⚠️ Failed to poll canvas after direct video', pollError)
          }
          await new Promise((resolve) => setTimeout(resolve, 1000))
        }

        if (!foundVideo) {
          console.warn('⚠️ Direct video completed but no video file found during fallback poll', {
            canvasId,
            sessionId,
          })
        }

        setPending(false)
      } catch (error) {
        console.error('Failed to send canvas video generation message:', error)
        toast.error('发起视频生成失败', {
          description: String(error),
        })
        setPending(false)
      }
    },
    [
      canvasId,
      messages,
      scrollToBottom,
      sessionId,
      setMessages,
      setPending,
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
