import { markStoryboardPrimaryVariant } from '@/api/storyboard'
import { Button } from '@/components/ui/button'
import { useCanvas } from '@/contexts/canvas'
import { TCanvasAddImagesToChatEvent } from '@/lib/event'
import { memo } from 'react'
import { toast } from 'sonner'

type CanvasStoryboardPrimarySelectorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const CanvasStoryboardPrimarySelector = ({
  selectedImages,
}: CanvasStoryboardPrimarySelectorProps) => {
  const { canvasId } = useCanvas()
  const selectedImage = selectedImages[0]

  const handleMarkPrimary = async () => {
    const fileId = String(
      selectedImage?.canvasFileId || selectedImage?.fileId || ''
    ).trim()

    if (!canvasId || !fileId) {
      toast.error('当前未找到可设置主版本的分镜图')
      return
    }

    try {
      const response = await markStoryboardPrimaryVariant({
        canvasId,
        fileId,
      })
      const shotId = String(response?.result?.shot_id || '')
      toast.success('已设为主版本', {
        description: shotId ? `镜头 ${shotId} 的主版本已更新` : undefined,
      })
      window.dispatchEvent(
        new CustomEvent('jaaz:refresh-canvas', {
          detail: {
            canvasId,
            reason: 'storyboard-mark-primary',
          },
        })
      )
    } catch (error) {
      console.error('Failed to mark storyboard primary variant:', error)
      toast.error('设置主版本失败', {
        description: String(error),
      })
    }
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleMarkPrimary}>
      设为主版本
    </Button>
  )
}

export default memo(CanvasStoryboardPrimarySelector)
