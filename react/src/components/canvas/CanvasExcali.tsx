import { saveCanvas } from '@/api/canvas'
import { useCanvas } from '@/contexts/canvas'
import useDebounce from '@/hooks/use-debounce'
import { useTheme } from '@/hooks/use-theme'
import { eventBus } from '@/lib/event'
import * as ISocket from '@/types/socket'
import { CanvasData } from '@/types/types'
import { Excalidraw, convertToExcalidrawElements } from '@excalidraw/excalidraw'
import {
  ExcalidrawImageElement,
  ExcalidrawEmbeddableElement,
  OrderedExcalidrawElement,
  Theme,
  NonDeleted,
} from '@excalidraw/excalidraw/element/types'
import '@excalidraw/excalidraw/index.css'
import {
  AppState,
  BinaryFileData,
  BinaryFiles,
  ExcalidrawInitialDataState,
} from '@excalidraw/excalidraw/types'
import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { VideoElement } from './VideoElement'

import '@/assets/style/canvas.css'

type LastImagePosition = {
  x: number
  y: number
  width: number
  height: number
  col: number // col index
}

type CanvasExcaliProps = {
  canvasId: string
  initialData?: ExcalidrawInitialDataState
}

const isVideoLink = (link?: string | null) => {
  if (!link) return false
  return (
    link.includes('.mp4') ||
    link.includes('.webm') ||
    link.includes('.ogg') ||
    link.startsWith('blob:') ||
    link.includes('video')
  )
}

const normalizeCanvasInitialData = (
  initialData?: ExcalidrawInitialDataState
): ExcalidrawInitialDataState | undefined => {
  if (!initialData || !Array.isArray(initialData.elements)) {
    return initialData
  }

  const files = (initialData.files || {}) as Record<string, BinaryFileData>
  const normalizedElements = initialData.elements.map((element) => {
    if (element.type !== 'video') {
      return element
    }

    const fileId = (element as { fileId?: string }).fileId
    const file = fileId ? files[fileId] : undefined
    const link = file?.dataURL
    if (!link) {
      return element
    }

    return {
      ...element,
      type: 'embeddable' as const,
      link,
      customData: {
        migratedFromVideo: true,
      },
    }
  })

  return {
    ...initialData,
    elements: normalizedElements,
  }
}

const stripCollaboratorsFromAppState = (
  appState?: AppState | ExcalidrawInitialDataState['appState']
) => {
  if (!appState) {
    return appState
  }

  const { collaborators: _collaborators, ...safeAppState } = appState as AppState & {
    collaborators?: unknown
  }
  return safeAppState
}

const buildSceneSyncSignature = (
  data?: ExcalidrawInitialDataState
): string => {
  if (!data) {
    return 'empty'
  }

  return JSON.stringify({
    elementIds: (data.elements || []).map((element) => ({
      id: element.id,
      type: element.type,
      updated: element.updated,
      version: element.version,
    })),
    fileIds: Object.keys(data.files || {}).sort(),
  })
}

const extractPersistedVideoState = (
  initialData?: ExcalidrawInitialDataState
) => {
  const normalizedData = normalizeCanvasInitialData(initialData)
  const normalizedFiles =
    (normalizedData?.files as Record<string, BinaryFileData> | undefined) || {}
  const persistedVideoElements: Record<string, any> = {}
  const persistedVideoFiles: Record<string, BinaryFileData> = {}

  for (const element of initialData?.elements || []) {
    if (element.type !== 'video') {
      continue
    }

    const fileId = (element as { fileId?: string }).fileId
    if (!fileId) {
      continue
    }

    persistedVideoElements[element.id] = element
    if (normalizedFiles[fileId]) {
      persistedVideoFiles[fileId] = normalizedFiles[fileId]
    }
  }

  return {
    elements: persistedVideoElements,
    files: persistedVideoFiles,
  }
}

const CanvasExcali: React.FC<CanvasExcaliProps> = ({
  canvasId,
  initialData,
}) => {
  const { excalidrawAPI, setExcalidrawAPI } = useCanvas()

  const { i18n } = useTranslation()

  // Immediate handler for UI updates (no debounce)
  const handleSelectionChange = (
    elements: Readonly<OrderedExcalidrawElement[]>,
    appState: AppState
  ) => {
    if (!appState) return

    // Check if any selected element is embeddable type
    const selectedElements = elements.filter((element) => 
      appState.selectedElementIds[element.id]
    )
    const hasEmbeddableSelected = selectedElements.some(
      (element) => element.type === 'embeddable'
    )

    // Toggle CSS class to hide/show left panel immediately
    const excalidrawContainer = document.querySelector('.excalidraw')
    if (excalidrawContainer) {
      if (hasEmbeddableSelected) {
        excalidrawContainer.classList.add('hide-left-panel')
      } else {
        excalidrawContainer.classList.remove('hide-left-panel')
      }
    }
  }

  // Debounced handler for saving (performance optimization)
  const handleSave = useDebounce(
    (
      elements: Readonly<OrderedExcalidrawElement[]>,
      appState: AppState,
      files: BinaryFiles
    ) => {
      if (elements.length === 0 || !appState) {
        return
      }

      const serializedVideoElements: Record<string, any> = {
        ...persistedVideoElementsRef.current,
      }
      const nonVideoElements = elements.filter((element) => {
        if (element.type !== 'embeddable') {
          return true
        }

        const embeddable = element as ExcalidrawEmbeddableElement
        if (!isVideoLink(embeddable.link)) {
          return true
        }

        const matchedFileEntry = Object.entries(files).find(([, file]) => {
          const dataUrl = String(file?.dataURL || '')
          return dataUrl === embeddable.link || embeddable.link?.includes(dataUrl)
        })
        const matchedFileId = matchedFileEntry?.[0]
        if (!matchedFileId) {
          return false
        }

        serializedVideoElements[embeddable.id] = {
          type: 'video',
          id: embeddable.id,
          x: embeddable.x,
          y: embeddable.y,
          width: embeddable.width,
          height: embeddable.height,
          angle: embeddable.angle,
          fileId: matchedFileId,
          strokeColor: embeddable.strokeColor,
          fillStyle: embeddable.fillStyle,
          strokeStyle: embeddable.strokeStyle,
          boundElements: embeddable.boundElements,
          roundness: embeddable.roundness,
          frameId: embeddable.frameId,
          backgroundColor: embeddable.backgroundColor,
          strokeWidth: embeddable.strokeWidth,
          roughness: embeddable.roughness,
          opacity: embeddable.opacity,
          groupIds: embeddable.groupIds,
          seed: embeddable.seed,
          version: embeddable.version,
          versionNonce: embeddable.versionNonce,
          isDeleted: embeddable.isDeleted,
          index: embeddable.index,
          updated: embeddable.updated,
          link: null,
          locked: embeddable.locked,
          status: 'saved',
          scale: [1, 1],
          crop: null,
        }
        return false
      })

      persistedVideoElementsRef.current = serializedVideoElements
      const mergedFiles = {
        ...files,
        ...persistedVideoFilesRef.current,
      }

      const data: CanvasData = {
        elements: [
          ...nonVideoElements,
          ...Object.values(serializedVideoElements),
        ],
        appState: stripCollaboratorsFromAppState(appState) as AppState,
        files: mergedFiles,
      }

      let thumbnail = ''
      const latestImage = elements
        .filter((element) => element.type === 'image')
        .sort((a, b) => b.updated - a.updated)[0]
      if (latestImage) {
        const file = mergedFiles[latestImage.fileId!]
        if (file) {
          thumbnail = file.dataURL
        }
      }

      saveCanvas(canvasId, { data, thumbnail })
    },
    1000
  )

  // Combined handler that calls both immediate and debounced functions
  const handleChange = (
    elements: Readonly<OrderedExcalidrawElement[]>,
    appState: AppState,
    files: BinaryFiles
  ) => {
    if (suppressNextSaveRef.current) {
      suppressNextSaveRef.current = false
      console.log('🖼️ Skipping one save after remote canvas sync', {
        canvasId,
      })
      return
    }

    // Immediate UI updates
    handleSelectionChange(elements, appState)
    // Debounced save operation
    handleSave(elements, appState, files)
  }

  const lastImagePosition = useRef<LastImagePosition | null>(
    localStorage.getItem('excalidraw-last-image-position')
      ? JSON.parse(localStorage.getItem('excalidraw-last-image-position')!)
      : null
  )
  const initialPersistedVideoState = extractPersistedVideoState(initialData)
  const persistedVideoElementsRef = useRef<Record<string, any>>(
    initialPersistedVideoState.elements
  )
  const persistedVideoFilesRef = useRef<Record<string, BinaryFileData>>(
    initialPersistedVideoState.files
  )
  const lastAppliedInitialDataSignatureRef = useRef<string>(
    buildSceneSyncSignature(normalizeCanvasInitialData(initialData))
  )
  const suppressNextSaveRef = useRef(false)
  const { theme } = useTheme()

  // 添加自定义类名以便应用我们的CSS修复
  const excalidrawClassName = `excalidraw-custom ${theme === 'dark' ? 'excalidraw-dark-fix-wm76394yjopk' : 'excalidraw-wm76394yjopk'}`
  
  // 在深色模式下使用自定义主题设置，避免使用默认的滤镜
  // 这样可以确保颜色在深色模式下正确显示
  const customTheme = theme === 'dark' ? 'light' : theme
  
  // 在组件挂载和主题变化时设置深色模式下的背景色
  useEffect(() => {
    if (excalidrawAPI && theme === 'dark') {
      // 设置深色背景，但保持light主题以避免颜色反转
      excalidrawAPI.updateScene({
        appState: {
          viewBackgroundColor: '#121212',
          gridColor: 'rgba(255, 255, 255, 0.1)',
        }
      })
    } else if (excalidrawAPI && theme === 'light') {
      // 恢复浅色背景
      excalidrawAPI.updateScene({
        appState: {
          viewBackgroundColor: '#ffffff',
          gridColor: 'rgba(0, 0, 0, 0.1)',
        }
      })
    }
  }, [excalidrawAPI, theme])

  useEffect(() => {
    const persistedVideoState = extractPersistedVideoState(initialData)
    persistedVideoElementsRef.current = persistedVideoState.elements
    persistedVideoFilesRef.current = persistedVideoState.files
  }, [initialData])

  useEffect(() => {
    if (!excalidrawAPI || !initialData) {
      return
    }

    const normalizedData = normalizeCanvasInitialData(initialData)
    const nextSignature = buildSceneSyncSignature(normalizedData)

    if (lastAppliedInitialDataSignatureRef.current === nextSignature) {
      return
    }
    lastAppliedInitialDataSignatureRef.current = nextSignature

    console.log('🖼️ Applying refreshed canvas data to Excalidraw scene', {
      canvasId,
      elementCount: normalizedData?.elements?.length ?? 0,
      fileCount: Object.keys(normalizedData?.files || {}).length,
    })

    const normalizedFiles = Object.values(
      (normalizedData?.files || {}) as Record<string, BinaryFileData>
    )
    if (normalizedFiles.length > 0) {
      excalidrawAPI.addFiles(normalizedFiles)
    }

    suppressNextSaveRef.current = true
    excalidrawAPI.updateScene({
      elements: normalizedData?.elements || [],
    })
  }, [canvasId, excalidrawAPI, initialData])

  const addImageToExcalidraw = useCallback(
    async (imageElement: ExcalidrawImageElement, file: BinaryFileData) => {
      if (!excalidrawAPI) return

      // 获取当前画布元素以便添加新元素
      const currentElements = excalidrawAPI.getSceneElements()

      excalidrawAPI.addFiles([file])

      console.log('👇 Adding new image element to canvas:', imageElement.id)
      console.log('👇 Image element properties:', {
        id: imageElement.id,
        type: imageElement.type,
        locked: imageElement.locked,
        groupIds: imageElement.groupIds,
        isDeleted: imageElement.isDeleted,
        x: imageElement.x,
        y: imageElement.y,
        width: imageElement.width,
        height: imageElement.height,
      })

      // Ensure image is not locked and can be manipulated
      const unlockedImageElement = {
        ...imageElement,
        locked: false,
        groupIds: [],
        isDeleted: false,
      }

      excalidrawAPI.updateScene({
        elements: [...(currentElements || []), unlockedImageElement],
      })

      localStorage.setItem(
        'excalidraw-last-image-position',
        JSON.stringify(lastImagePosition.current)
      )
    },
    [excalidrawAPI]
  )

  const addVideoEmbed = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async (elementData: any, videoSrc: string) => {
      if (!excalidrawAPI) return

      // Function to create video element with given dimensions
      const createVideoElement = (finalWidth: number, finalHeight: number) => {
        console.log('👇 Video element properties:', {
          id: elementData.id,
          type: elementData.type,
          locked: elementData.locked,
          groupIds: elementData.groupIds,
          isDeleted: elementData.isDeleted,
          x: elementData.x,
          y: elementData.y,
          width: elementData.width,
          height: elementData.height,
        })

        const videoElements = convertToExcalidrawElements([
          {
            type: 'embeddable',
            id: elementData.id,
            x: elementData.x,
            y: elementData.y,
            width: elementData.width,
            height: elementData.height,
            link: videoSrc,
            // 添加必需的基本样式属性
            strokeColor: '#000000',
            backgroundColor: 'transparent',
            fillStyle: 'solid',
            strokeWidth: 1,
            strokeStyle: 'solid',
            roundness: null,
            roughness: 1,
            opacity: 100,
            // 添加必需的变换属性
            angle: 0,
            seed: Math.random(),
            version: 1,
            versionNonce: Math.random(),
            // 添加必需的状态属性
            locked: false,
            isDeleted: false,
            groupIds: [],
            // 添加绑定框属性
            boundElements: [],
            updated: Date.now(),
            // 添加必需的索引和帧ID属性
            frameId: null,
            index: null, // 添加缺失的index属性
            // 添加自定义数据属性
            customData: {},
          },
        ])

        console.log('👇 Converted video elements:', videoElements)

      const currentElements = excalidrawAPI.getSceneElements()
      const newElementId = videoElements[0]?.id || elementData.id
      const newElements = [
        ...currentElements.filter((element) => element.id !== newElementId),
        ...videoElements,
      ]

        console.log(
          '👇 Updating scene with elements count:',
          newElements.length
        )

        excalidrawAPI.updateScene({
          elements: newElements,
          appState: {
            selectedElementIds: {
              [newElementId]: true,
            },
          },
        })

        setTimeout(() => {
          excalidrawAPI.scrollToContent(newElementId, { animate: true })
        }, 50)

        console.log(
          '👇 Added video embed element:',
          videoSrc,
          `${elementData.width}x${elementData.height}`
        )
      }

      // If dimensions are provided, use them directly
      if (elementData.width && elementData.height) {
        createVideoElement(elementData.width, elementData.height)
        return
      }

      // Otherwise, try to get video's natural dimensions
      const video = document.createElement('video')
      video.crossOrigin = 'anonymous'

      video.onloadedmetadata = () => {
        const videoWidth = video.videoWidth
        const videoHeight = video.videoHeight

        if (videoWidth && videoHeight) {
          // Scale down if video is too large (max 800px width)
          const maxWidth = 800
          let finalWidth = videoWidth
          let finalHeight = videoHeight

          if (videoWidth > maxWidth) {
            const scale = maxWidth / videoWidth
            finalWidth = maxWidth
            finalHeight = videoHeight * scale
          }

          createVideoElement(finalWidth, finalHeight)
        } else {
          // Fallback to default dimensions
          createVideoElement(320, 180)
        }
      }

      video.onerror = () => {
        console.warn('Could not load video metadata, using default dimensions')
        createVideoElement(320, 180)
      }

      video.src = videoSrc
    },
    [excalidrawAPI]
  )

  const renderEmbeddable = useCallback(
    (element: NonDeleted<ExcalidrawEmbeddableElement>, appState: AppState) => {
      const { link } = element

      // Check if this is a video URL
      if (isVideoLink(link)) {
        // Return the VideoPlayer component
        return (
          <VideoElement
            src={link}
            width={element.width}
            height={element.height}
          />
        )
      }

      console.log('👇 Not a video URL, returning null for:', link)
      // Return null for non-video embeds to use default rendering
      return null
    },
    []
  )

  const handleImageGenerated = useCallback(
    (imageData: ISocket.SessionImageGeneratedEvent) => {
      console.log('👇 CanvasExcali received image_generated:', imageData)

      // Only handle if it's for this canvas
      if (imageData.canvas_id !== canvasId) {
        console.log('👇 Image not for this canvas, ignoring')
        return
      }

      // Check if this is actually a video generation event that got mislabeled
      if (imageData.file?.mimeType?.startsWith('video/')) {
        console.log(
          '👇 This appears to be a video, not an image. Ignoring in image handler.'
        )
        return
      }

      addImageToExcalidraw(imageData.element, imageData.file)
    },
    [addImageToExcalidraw, canvasId]
  )

  const handleVideoGenerated = useCallback(
    (videoData: ISocket.SessionVideoGeneratedEvent) => {
      console.log('👇 CanvasExcali received video_generated:', videoData)

      // Only handle if it's for this canvas
      if (videoData.canvas_id !== canvasId) {
        console.log('👇 Video not for this canvas, ignoring')
        return
      }

      persistedVideoElementsRef.current[videoData.element.id] = videoData.element
      persistedVideoFilesRef.current[videoData.file.id] = videoData.file

      // Create video embed element using the video URL
      addVideoEmbed(videoData.element, videoData.video_url)
    },
    [addVideoEmbed, canvasId]
  )

  useEffect(() => {
    eventBus.on('Socket::Session::ImageGenerated', handleImageGenerated)
    eventBus.on('Socket::Session::VideoGenerated', handleVideoGenerated)
    return () => {
      eventBus.off('Socket::Session::ImageGenerated', handleImageGenerated)
      eventBus.off('Socket::Session::VideoGenerated', handleVideoGenerated)
    }
  }, [handleImageGenerated, handleVideoGenerated])

  return (
    <Excalidraw
      theme={customTheme as Theme}
      langCode={i18n.language}
      className={excalidrawClassName}
      excalidrawAPI={(api) => {
        setExcalidrawAPI(api)
      }}
      onChange={handleChange}
      initialData={() => {
        const data = normalizeCanvasInitialData(initialData)
        console.log('👇initialData', data)
        if (!data) {
          return null
        }

        return {
          ...data,
          appState: stripCollaboratorsFromAppState(data.appState),
        }
      }}
      renderEmbeddable={renderEmbeddable}
      // Allow all URLs for embeddable content
      validateEmbeddable={(url: string) => {
        console.log('👇 Validating embeddable URL:', url)
        // Allow all URLs - return true for everything
        return true
      }}
      // Ensure interactive mode is enabled
      viewModeEnabled={false}
      zenModeEnabled={false}
      // Allow element manipulation
      onPointerUpdate={(payload) => {
        // Minimal logging - only log significant pointer events
        if (payload.button === 'down' && Math.random() < 0.05) {
          // console.log('👇 Pointer down on:', payload.pointer.x, payload.pointer.y)
        }
      }}
    />
  )
}

export { CanvasExcali }
export default CanvasExcali
