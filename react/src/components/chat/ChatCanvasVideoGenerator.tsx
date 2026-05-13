import { sendDirectVideoGenerate } from '@/api/video'
import { getCanvas } from '@/api/canvas'
import { uploadImage } from '@/api/upload'
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasGenerateVideoEvent } from '@/lib/event'
import { dataURLToFile } from '@/lib/utils'
import { Message, PendingType } from '@/types/types'
import { useCallback, useEffect, useRef } from 'react'
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
  const { textModel } = useConfigs()
  const inFlightRef = useRef(false)

  const handleGenerateVideo = useCallback(
    async (data: TCanvasGenerateVideoEvent) => {
      if (inFlightRef.current) {
        toast.info('视频生成正在进行中，请等待当前任务完成')
        return
      }

      const selectedImages = data.selectedImages.slice(0, MAX_REFERENCE_IMAGES)
      if (selectedImages.length === 0) {
        return
      }

      inFlightRef.current = true
      setPending('text')

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
              text: data.userPrompt,
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
          textModel,
          fileIds: resolvedImages.map((image) => image.fileId),
          prompt: data.finalPrompt,
          duration,
          aspectRatio: data.aspectRatio,
          resolution: data.resolution,
          selectionMode: 'start_end_frames',
          startFrameFileId: startFrame.fileId,
          endFrameFileId: endFrame.fileId,
          skipPromptConfirmation: true,
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
                new CustomEvent('app:refresh-canvas', {
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
      setPending,
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
