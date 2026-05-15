import { listCanvasGenerationJobs, sendDirectVideoGenerate } from '@/api/video'
import { getCanvas } from '@/api/canvas'
import { uploadImage } from '@/api/upload'
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasGenerateVideoEvent, TEvents } from '@/lib/event'
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
  const activeJobIdRef = useRef<string | null>(null)

  const isMatchingVideoJobEvent = useCallback(
    (
      data:
        | TEvents['Socket::Session::JobQueued']
        | TEvents['Socket::Session::JobRunning']
        | TEvents['Socket::Session::JobProgress']
        | TEvents['Socket::Session::JobSucceeded']
        | TEvents['Socket::Session::JobFailed']
    ) => {
      return (
        data.canvas_id === canvasId &&
        data.session_id === sessionId &&
        data.job_type === 'direct_video'
      )
    },
    [canvasId, sessionId]
  )

  const handleGenerateVideo = useCallback(
    async (data: TCanvasGenerateVideoEvent) => {
      if (inFlightRef.current || activeJobIdRef.current) {
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
        activeJobIdRef.current = response.job_id
        setPending('text')
        toast.success('视频任务已提交', {
          description:
            response.job.status === 'queued'
              ? '任务已进入队列'
              : '任务已开始生成',
        })
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
    const handleJobQueued = (data: TEvents['Socket::Session::JobQueued']) => {
      if (!isMatchingVideoJobEvent(data)) {
        return
      }
      activeJobIdRef.current = data.job_id
      setPending('text')
    }

    const handleJobRunning = (data: TEvents['Socket::Session::JobRunning']) => {
      if (!isMatchingVideoJobEvent(data)) {
        return
      }
      activeJobIdRef.current = data.job_id
      setPending('text')
    }

    const handleJobProgress = (data: TEvents['Socket::Session::JobProgress']) => {
      if (!isMatchingVideoJobEvent(data)) {
        return
      }
      activeJobIdRef.current = data.job_id
      setPending('text')
    }

    const handleJobSucceeded = (data: TEvents['Socket::Session::JobSucceeded']) => {
      if (!isMatchingVideoJobEvent(data)) {
        return
      }
      activeJobIdRef.current = null
      setPending(false)
      window.dispatchEvent(
        new CustomEvent('app:refresh-canvas', {
          detail: {
            canvasId,
            reason: 'direct-video-job-succeeded',
          },
        })
      )
    }

    const handleJobFailed = (data: TEvents['Socket::Session::JobFailed']) => {
      if (!isMatchingVideoJobEvent(data)) {
        return
      }
      activeJobIdRef.current = null
      setPending(false)
      toast.error('视频生成失败', {
        description: data.error_message || '后台任务执行失败',
      })
    }

    eventBus.on('Canvas::GenerateVideo', handleGenerateVideo)
    eventBus.on('Socket::Session::JobQueued', handleJobQueued)
    eventBus.on('Socket::Session::JobRunning', handleJobRunning)
    eventBus.on('Socket::Session::JobProgress', handleJobProgress)
    eventBus.on('Socket::Session::JobSucceeded', handleJobSucceeded)
    eventBus.on('Socket::Session::JobFailed', handleJobFailed)

    return () => {
      eventBus.off('Canvas::GenerateVideo', handleGenerateVideo)
      eventBus.off('Socket::Session::JobQueued', handleJobQueued)
      eventBus.off('Socket::Session::JobRunning', handleJobRunning)
      eventBus.off('Socket::Session::JobProgress', handleJobProgress)
      eventBus.off('Socket::Session::JobSucceeded', handleJobSucceeded)
      eventBus.off('Socket::Session::JobFailed', handleJobFailed)
    }
  }, [canvasId, handleGenerateVideo, isMatchingVideoJobEvent, setPending])

  useEffect(() => {
    let mounted = true

    const restoreActiveJobs = async () => {
      try {
        const response = await listCanvasGenerationJobs(canvasId, {
          type: 'direct_video',
          status: 'queued,running',
          limit: 20,
        })
        if (!mounted) {
          return
        }
        const activeJob = response.jobs.find((job) => job.session_id === sessionId)
        if (!activeJob) {
          return
        }
        activeJobIdRef.current = activeJob.id
        setPending('text')
      } catch (error) {
        console.warn('⚠️ Failed to restore active direct video jobs', error)
      }
    }

    restoreActiveJobs()

    return () => {
      mounted = false
    }
  }, [canvasId, sessionId, setPending])

  return null
}

export default ChatCanvasVideoGenerator
