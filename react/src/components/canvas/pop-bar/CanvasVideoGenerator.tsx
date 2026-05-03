import { Button } from '@/components/ui/button'
import { useCanvas } from '@/contexts/canvas'
import { eventBus, TCanvasAddImagesToChatEvent } from '@/lib/event'
import { toast } from 'sonner'
import { memo } from 'react'
import { useTranslation } from 'react-i18next'

type CanvasVideoGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const MAX_REFERENCE_IMAGES = 2
const DEFAULT_VIDEO_PROMPT =
  '基于这些参考图生成一个 6 秒视频，16:9，1080p，镜头缓慢推进'

const getConfiguredVideoModel = async () => {
  const response = await fetch('/api/config')
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`)
  }
  const config = await response.json()
  return String(config?.apipodvideo?.model_name || '')
}

const CanvasVideoGenerator = ({
  selectedImages,
}: CanvasVideoGeneratorProps) => {
  const { t } = useTranslation()
  const { excalidrawAPI } = useCanvas()

  const handleGenerateVideo = async () => {
    if (selectedImages.length === 0) {
      toast.warning('请先选中一张图片')
      return
    }

    const normalizedSelectedImages = selectedImages.slice(0, MAX_REFERENCE_IMAGES)
    if (selectedImages.length > MAX_REFERENCE_IMAGES) {
      toast.info('Veo 3.1 Fast 最多使用 2 张参考图，当前仅取前 2 张')
    }

    try {
      const configuredModelName = await getConfiguredVideoModel()
      if (
        normalizedSelectedImages.length > 1 &&
        configuredModelName &&
        configuredModelName !== 'veo3-1-fast'
      ) {
        toast.error('当前视频模型不支持多图参考', {
          description: `${configuredModelName} 仅支持 0 或 1 张参考图。请选择 1 张图片，或切换到 veo3-1-fast。`,
        })
        return
      }
    } catch (error) {
      console.error('Failed to inspect video model config:', error)
    }

    eventBus.emit('Canvas::GenerateVideo', {
      selectedImages: normalizedSelectedImages,
      prompt: DEFAULT_VIDEO_PROMPT,
      duration: 6,
      aspectRatio: '16:9',
      resolution: '1080p',
    })

    excalidrawAPI?.updateScene({
      appState: { selectedElementIds: {} },
    })
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleGenerateVideo}>
      {t('canvas:popbar.generateVideo')}
    </Button>
  )
}

export default memo(CanvasVideoGenerator)
