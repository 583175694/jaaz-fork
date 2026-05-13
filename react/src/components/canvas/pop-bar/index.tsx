import { useCanvas } from '@/contexts/canvas'
import { TCanvasAddImagesToChatEvent } from '@/lib/event'
import { ExcalidrawImageElement } from '@excalidraw/excalidraw/element/types'
import { AnimatePresence } from 'motion/react'
import { useRef, useState } from 'react'
import CanvasPopbarContainer from './CanvasPopbarContainer'

const CanvasPopbarWrapper = () => {
  const { excalidrawAPI } = useCanvas()

  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const [showAddToChat, setShowAddToChat] = useState(false)
  const [showGenerateVideo, setShowGenerateVideo] = useState(false)
  const [showGenerateStoryboard, setShowGenerateStoryboard] = useState(false)
  const [showGenerateMultiview, setShowGenerateMultiview] = useState(false)

  const selectedImagesRef = useRef<TCanvasAddImagesToChatEvent>([])

  excalidrawAPI?.onChange((elements, appState, files) => {
    const selectedIds = appState.selectedElementIds
    if (Object.keys(selectedIds).length === 0) {
      setPos(null)
      setShowAddToChat(false)
      setShowGenerateVideo(false)
      setShowGenerateStoryboard(false)
      setShowGenerateMultiview(false)
      return
    }

    const selectedImages = elements.filter(
      (element) => element.type === 'image' && selectedIds[element.id]
    ) as ExcalidrawImageElement[]

    // 判断是否显示添加到对话按钮：选中图片元素
    const hasSelectedImages = selectedImages.length > 0
    const hasSingleSelectedImage = selectedImages.length === 1
    setShowAddToChat(hasSelectedImages)
    setShowGenerateVideo(hasSelectedImages)
    setShowGenerateStoryboard(hasSingleSelectedImage)
    setShowGenerateMultiview(hasSingleSelectedImage)

    if (!hasSelectedImages) {
      setPos(null)
      return
    }

    // 处理选中的图片数据
    selectedImagesRef.current = selectedImages
      .filter((image) => image.fileId)
      .map((image) => {
        const file = files[image.fileId!]
        const isBase64 = file.dataURL.startsWith('data:')
        const id = isBase64 ? file.id : file.dataURL.split('/').at(-1)!
        return {
          fileId: id,
          canvasFileId: file.id,
          base64: file.dataURL,
          width: image.width,
          height: image.height,
          x: image.x,
          y: image.y,
        }
      })

    const centerX =
      selectedImages.reduce((acc, image) => acc + image.x + image.width / 2, 0) /
      selectedImages.length

    const bottomY = selectedImages.reduce(
      (acc, image) => Math.max(acc, image.y + image.height),
      Number.NEGATIVE_INFINITY
    )

    const scrollX = appState.scrollX
    const scrollY = appState.scrollY
    const zoom = appState.zoom.value
    const offsetX = (scrollX + centerX) * zoom
    const offsetY = (scrollY + bottomY) * zoom
    setPos({ x: offsetX, y: offsetY })
    // console.log(offsetX, offsetY)
  })

  return (
    <div className='absolute left-0 bottom-0 w-full h-full z-20 pointer-events-none'>
      <AnimatePresence>
        {pos && showAddToChat && (
          <CanvasPopbarContainer
            pos={pos}
            selectedImages={selectedImagesRef.current}
            showAddToChat={showAddToChat}
            showGenerateVideo={showGenerateVideo}
            showGenerateStoryboard={showGenerateStoryboard}
            showGenerateMultiview={showGenerateMultiview}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

export default CanvasPopbarWrapper
