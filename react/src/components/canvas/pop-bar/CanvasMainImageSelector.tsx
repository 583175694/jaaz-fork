import { Button } from '@/components/ui/button'
import { setCurrentMainImage } from '@/api/canvas'
import { useCanvas } from '@/contexts/canvas'
import { TCanvasAddImagesToChatEvent } from '@/lib/event'
import { memo } from 'react'
import { toast } from 'sonner'

type CanvasMainImageSelectorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const CanvasMainImageSelector = ({
  selectedImages,
}: CanvasMainImageSelectorProps) => {
  const { canvasId, mainImageFileId, setMainImageFileId } = useCanvas()
  const selectedImage = selectedImages[0]
  const canvasFileId = String(
    selectedImage?.canvasFileId || selectedImage?.fileId || ''
  ).trim()
  const isCurrentMainImage = !!canvasFileId && canvasFileId === mainImageFileId

  const handleSetMainImage = async () => {
    if (!canvasFileId) {
      toast.error('当前图片无法设为主图')
      return
    }

    if (canvasId) {
      await setCurrentMainImage(canvasId, canvasFileId)
    }
    setMainImageFileId(canvasFileId)
    window.dispatchEvent(
      new CustomEvent('jaaz:refresh-canvas', {
        detail: {
          canvasId,
          reason: 'main-image-updated',
        },
      })
    )
    toast.success('已设为主图', {
      description: '后续分镜生成会默认把这张图视为视觉母版和连续性锚点。',
    })
  }

  return (
    <Button
      variant={isCurrentMainImage ? 'default' : 'ghost'}
      size="sm"
      onClick={handleSetMainImage}
    >
      {isCurrentMainImage ? '当前主图' : '设为主图'}
    </Button>
  )
}

export default memo(CanvasMainImageSelector)
