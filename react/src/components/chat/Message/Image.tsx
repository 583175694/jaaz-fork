import { Button } from '@/components/ui/button'
import { useCanvas } from '@/contexts/canvas'
import { useTranslation } from 'react-i18next'
import { PhotoView } from 'react-photo-view'
import { useMemo } from 'react'

type MessageImageProps = {
  content: {
    image_url: {
      url: string
    }
    type: 'image_url'
  }
}

const MessageImage = ({ content }: MessageImageProps) => {
  const { excalidrawAPI } = useCanvas()
  const files = excalidrawAPI?.getFiles()
  const fileUrlIndex = useMemo(() => {
    const index = new Map<string, string>()
    Object.keys(files || {}).forEach((key) => {
      const url = files?.[key]?.dataURL
      if (!url) {
        return
      }
      index.set(String(url), key)
      index.set(`/api/file/${key}`, key)
    })
    return index
  }, [files])

  const { t } = useTranslation()

  const handleImagePositioning = (id: string) => {
    excalidrawAPI?.scrollToContent(id, { animate: true })
  }
  const imageUrl = String(content.image_url.url || '')
  const id =
    fileUrlIndex.get(imageUrl) ||
    Array.from(fileUrlIndex.entries()).find(([url]) => imageUrl.includes(url))?.[1]

  return (
    <div className="w-full max-w-[140px]">
      <PhotoView src={imageUrl}>
        <div className="relative group cursor-pointer">
          <img
            className="w-full h-auto max-h-[140px] object-cover rounded-md border border-border hover:scale-105 transition-transform duration-300"
            src={imageUrl}
            alt="Image"
          />

          {id && (
            <Button
              variant="secondary"
              size="sm"
              className="group-hover:opacity-100 opacity-0 absolute top-2 right-2 z-10 text-xs"
              onClick={(e) => {
                e.stopPropagation()
                handleImagePositioning(id)
              }}
            >
              {t('chat:messages:imagePositioning')}
            </Button>
          )}
        </div>
      </PhotoView>
    </div>
  )
}

export default MessageImage
