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
  UIOptions,
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

type StoryboardDecoration = {
  storyboardId: string
  shotId: string
  variantId: string
  narrativeRole: string
  isPrimaryVariant: boolean
  x: number
  y: number
  width: number
  height: number
}

const STORYBOARD_ROLE_LABELS: Record<string, string> = {
  establishing: '建立镜头',
  progression: '推进镜头',
  reaction: '反应镜头',
  closure: '收束镜头',
  visual_mother_frame: '参考图',
}

const CANVAS_ALLOWED_TOOLS = new Set(['selection', 'hand'])
const BLOCKED_CANVAS_SHORTCUTS = new Set([
  'r',
  'o',
  'a',
  'l',
  'p',
  'd',
  't',
  'e',
  'x',
  'i',
])

const CANVAS_UI_OPTIONS: Partial<UIOptions> = {
  tools: {
    image: false,
  },
  canvasActions: {
    changeViewBackgroundColor: false,
    clearCanvas: false,
    export: false,
    loadScene: false,
    saveToActiveFile: false,
    saveAsImage: false,
    toggleTheme: false,
  },
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
    if (element.type === 'image') {
      const fileId = (element as { fileId?: string }).fileId
      const file = fileId ? files[fileId] : undefined
      return {
        ...element,
        locked: true,
        status: file?.dataURL ? 'saved' : element.status,
      }
    }

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
      locked: true,
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

const sanitizePersistedAppState = (
  appState?: AppState | ExcalidrawInitialDataState['appState'],
  options?: {
    dropViewport?: boolean
    dropCanvasMetrics?: boolean
  }
) => {
  const safeAppState = stripCollaboratorsFromAppState(appState) as
    | (Partial<AppState> & Record<string, unknown>)
    | undefined
  if (!safeAppState) {
    return safeAppState
  }

  const {
    width: _width,
    height: _height,
    offsetTop: _offsetTop,
    offsetLeft: _offsetLeft,
    selectedElementIds: _selectedElementIds,
    selectedGroupIds: _selectedGroupIds,
    previousSelectedElementIds: _previousSelectedElementIds,
    hoveredElementIds: _hoveredElementIds,
    editingTextElement: _editingTextElement,
    editingGroupId: _editingGroupId,
    editingLinearElement: _editingLinearElement,
    editingFrame: _editingFrame,
    activeEmbeddable: _activeEmbeddable,
    newElement: _newElement,
    multiElement: _multiElement,
    resizingElement: _resizingElement,
    selectionElement: _selectionElement,
    selectedElementsAreBeingDragged: _selectedElementsAreBeingDragged,
    openMenu: _openMenu,
    openPopup: _openPopup,
    openSidebar: _openSidebar,
    openDialog: _openDialog,
    contextMenu: _contextMenu,
    toast: _toast,
    searchMatches: _searchMatches,
    suggestedBindings: _suggestedBindings,
    startBoundElement: _startBoundElement,
    snapLines: _snapLines,
    originSnapOffset: _originSnapOffset,
    userToFollow: _userToFollow,
    followedBy: _followedBy,
    isLoading: _isLoading,
    isResizing: _isResizing,
    isRotating: _isRotating,
    isCropping: _isCropping,
    croppingElementId: _croppingElementId,
    scrolledOutside: _scrolledOutside,
    showWelcomeScreen: _showWelcomeScreen,
    pasteDialog: _pasteDialog,
    pendingImageElementId: _pendingImageElementId,
    fileHandle: _fileHandle,
    ...persistedAppState
  } = safeAppState

  let sanitizedAppState = persistedAppState

  if (options?.dropViewport) {
    const {
      scrollX: _scrollX,
      scrollY: _scrollY,
      zoom: _zoom,
      ...withoutViewport
    } = sanitizedAppState
    sanitizedAppState = withoutViewport
  }

  if (options?.dropCanvasMetrics) {
    const {
      width: _persistedWidth,
      height: _persistedHeight,
      offsetTop: _persistedOffsetTop,
      offsetLeft: _persistedOffsetLeft,
      ...withoutCanvasMetrics
    } = sanitizedAppState
    sanitizedAppState = withoutCanvasMetrics
  }

  return sanitizedAppState
}

const shouldResetViewportOnLoad = (data?: ExcalidrawInitialDataState) => {
  const appState = data?.appState as
    | (AppState & {
        width?: number
        height?: number
        scrollX?: number
        scrollY?: number
        zoom?: { value?: number }
      })
    | undefined

  if (!appState) {
    return false
  }

  const width = Number(appState.width || 0)
  const height = Number(appState.height || 0)
  const zoomValue = Number(appState.zoom?.value || 0)

  if (width <= 0 || height <= 0) {
    return true
  }

  if (!Number.isFinite(zoomValue) || zoomValue <= 0) {
    return true
  }

  const drawableElements = (data?.elements || []).filter(
    (element) =>
      !element.isDeleted &&
      !isStoryboardDecorationElement(element as { customData?: any })
  )
  if (!drawableElements.length) {
    return false
  }

  const bounds = drawableElements.reduce(
    (acc, element) => {
      const x = Number(element.x || 0)
      const y = Number(element.y || 0)
      const width = Number((element as { width?: number }).width || 0)
      const height = Number((element as { height?: number }).height || 0)
      return {
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x + width),
        maxY: Math.max(acc.maxY, y + height),
      }
    },
    {
      minX: Number.POSITIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    }
  )

  const sceneCenterX = (bounds.minX + bounds.maxX) / 2
  const sceneCenterY = (bounds.minY + bounds.maxY) / 2
  const viewportCenterX = -Number(appState.scrollX || 0) + width / (2 * zoomValue)
  const viewportCenterY =
    -Number(appState.scrollY || 0) + height / (2 * zoomValue)
  const sceneWidth = Math.max(bounds.maxX - bounds.minX, 1)
  const sceneHeight = Math.max(bounds.maxY - bounds.minY, 1)

  return (
    Math.abs(viewportCenterX - sceneCenterX) > sceneWidth * 1.5 ||
    Math.abs(viewportCenterY - sceneCenterY) > sceneHeight * 1.5
  )
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

const buildViewportSyncSignature = (
  data?: ExcalidrawInitialDataState
): string => {
  if (!data) {
    return 'empty'
  }

  const elements = (data.elements || []).filter(
    (element) => !isStoryboardDecorationElement(element as { customData?: any })
  )

  if (!elements.length) {
    return 'no-elements'
  }

  const bounds = elements.reduce(
    (acc, element) => {
      const x = Number(element.x || 0)
      const y = Number(element.y || 0)
      const width = Number((element as { width?: number }).width || 0)
      const height = Number((element as { height?: number }).height || 0)
      return {
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x + width),
        maxY: Math.max(acc.maxY, y + height),
      }
    },
    {
      minX: Number.POSITIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    }
  )

  return JSON.stringify(bounds)
}

const isStoryboardDecorationElement = (element: { customData?: any }) => {
  return Boolean(element?.customData?.storyboardDecoration)
}

const buildStoryboardDecorations = (
  data?: ExcalidrawInitialDataState,
  mainImageFileId?: string
): OrderedExcalidrawElement[] => {
  if (!data?.elements?.length || !data?.files) {
    return []
  }

  const files = data.files as Record<string, BinaryFileData>
  const imageElements = (data.elements as OrderedExcalidrawElement[]).filter(
    (element) => element.type === 'image'
  ) as ExcalidrawImageElement[]
  const imageByFileId = new Map<string, ExcalidrawImageElement>()
  for (const element of imageElements) {
    if (element.fileId) {
      imageByFileId.set(element.fileId, element)
    }
  }

  const groups = new Map<string, StoryboardDecoration[]>()
  for (const [fileId, file] of Object.entries(files)) {
    const storyboardMeta = (file as { storyboardMeta?: Record<string, unknown> })
      ?.storyboardMeta
    if (!storyboardMeta || typeof storyboardMeta !== 'object') {
      continue
    }

    const shotId = String(storyboardMeta.shot_id || '').trim()
    const storyboardId = String(storyboardMeta.storyboard_id || '').trim()
    const variantId = String(storyboardMeta.variant_id || '').trim()
    if (!shotId || !storyboardId || !variantId) {
      continue
    }

    const image = imageByFileId.get(fileId)
    if (!image) {
      continue
    }

    const groupKey = `${storyboardId}:${shotId}`
    if (!groups.has(groupKey)) {
      groups.set(groupKey, [])
    }

    groups.get(groupKey)!.push({
      storyboardId,
      shotId,
      variantId,
      narrativeRole: String(storyboardMeta.narrative_role || '').trim(),
      isPrimaryVariant: Boolean(storyboardMeta.is_primary_variant),
      x: image.x,
      y: image.y,
      width: image.width,
      height: image.height,
    })
  }

  if (mainImageFileId) {
    const mainImage = imageByFileId.get(mainImageFileId)
    if (mainImage) {
      groups.set(`main:${mainImageFileId}`, [
        {
          storyboardId: 'main',
          shotId: '主图',
          variantId: 'main',
          narrativeRole: 'visual_mother_frame',
          isPrimaryVariant: true,
          x: mainImage.x,
          y: mainImage.y,
          width: mainImage.width,
          height: mainImage.height,
        },
      ])
    }
  }

  const decorations: OrderedExcalidrawElement[] = []

  Array.from(groups.values()).forEach((items) => {
    if (!items.length) {
      return
    }

    const sortedItems = [...items].sort((a, b) => a.x - b.x)
    const primaryItem =
      sortedItems.find((item) => item.isPrimaryVariant) || sortedItems[0]
    const isMainGroup = primaryItem.storyboardId === 'main'
    const minX = Math.min(...sortedItems.map((item) => item.x))
    const minY = Math.min(...sortedItems.map((item) => item.y))
    const maxX = Math.max(...sortedItems.map((item) => item.x + item.width))
    const maxY = Math.max(...sortedItems.map((item) => item.y + item.height))
    const groupLabelText = isMainGroup
      ? '参考图'
      : `${primaryItem.shotId} · ${
          STORYBOARD_ROLE_LABELS[primaryItem.narrativeRole] ||
          primaryItem.narrativeRole ||
          'storyboard'
        } · ${
          sortedItems.length
        } 候选`
    const groupBorderId = isMainGroup
      ? `storyboard-decoration-group-main-${primaryItem.shotId}`
      : `storyboard-decoration-group-${primaryItem.storyboardId}-${primaryItem.shotId}`
    const groupLabelId = isMainGroup
      ? `storyboard-decoration-group-label-main-${primaryItem.shotId}`
      : `storyboard-decoration-group-label-${primaryItem.storyboardId}-${primaryItem.shotId}`
    const primaryBorderId = isMainGroup
      ? ''
      : `storyboard-decoration-primary-${primaryItem.storyboardId}-${primaryItem.shotId}-${primaryItem.variantId}`
    const primaryLabelId = isMainGroup
      ? ''
      : `storyboard-decoration-primary-label-${primaryItem.storyboardId}-${primaryItem.shotId}-${primaryItem.variantId}`

    const groupElements = [
      {
        type: 'rectangle',
        id: groupBorderId,
        x: minX - 14,
        y: minY - 42,
        width: maxX - minX + 28,
        height: maxY - minY + 56,
        angle: 0,
        strokeColor: isMainGroup ? '#10b981' : '#60a5fa',
        backgroundColor: 'transparent',
        fillStyle: 'solid',
        strokeWidth: isMainGroup ? 2.5 : 1.5,
        strokeStyle: isMainGroup ? 'solid' : 'dashed',
        roundness: null,
        roughness: 0,
        opacity: 100,
        seed: Math.random(),
        version: 1,
        versionNonce: Math.random(),
        isDeleted: false,
        groupIds: [],
        boundElements: [],
        updated: Date.now(),
        frameId: null,
        index: null,
        locked: true,
        link: null,
        customData: {
          storyboardDecoration: 'shot-group-border',
          storyboardId: primaryItem.storyboardId,
          shotId: primaryItem.shotId,
        },
      } as any,
      {
        type: 'text',
        id: groupLabelId,
        x: minX,
        y: minY - 32,
        width: Math.max(220, maxX - minX),
        height: 24,
        angle: 0,
        text: groupLabelText,
        fontSize: 16,
        fontFamily: 1,
        textAlign: 'left',
        verticalAlign: 'top',
        strokeColor: isMainGroup ? '#065f46' : '#1d4ed8',
        backgroundColor: 'transparent',
        fillStyle: 'solid',
        strokeWidth: 1,
        strokeStyle: 'solid',
        roundness: null,
        roughness: 0,
        opacity: 100,
        seed: Math.random(),
        version: 1,
        versionNonce: Math.random(),
        isDeleted: false,
        groupIds: [],
        boundElements: [],
        updated: Date.now(),
        frameId: null,
        index: null,
        locked: true,
        link: null,
        customData: {
          storyboardDecoration: 'shot-group-label',
          storyboardId: primaryItem.storyboardId,
          shotId: primaryItem.shotId,
        },
      } as any,
    ]

    const primaryElements = isMainGroup
      ? []
      : [
          {
            type: 'rectangle',
            id: primaryBorderId,
            x: primaryItem.x - 8,
            y: primaryItem.y - 8,
            width: primaryItem.width + 16,
            height: primaryItem.height + 16,
            angle: 0,
            strokeColor: '#f59e0b',
            backgroundColor: 'transparent',
            fillStyle: 'solid',
            strokeWidth: 2.5,
            strokeStyle: 'solid',
            roundness: null,
            roughness: 0,
            opacity: 100,
            seed: Math.random(),
            version: 1,
            versionNonce: Math.random(),
            isDeleted: false,
            groupIds: [],
            boundElements: [],
            updated: Date.now(),
            frameId: null,
            index: null,
            locked: true,
            link: null,
            customData: {
              storyboardDecoration: 'primary-variant-border',
              storyboardId: primaryItem.storyboardId,
              shotId: primaryItem.shotId,
              variantId: primaryItem.variantId,
            },
          } as any,
          {
            type: 'text',
            id: primaryLabelId,
            x: primaryItem.x,
            y: primaryItem.y + primaryItem.height + 8,
            width: Math.max(180, primaryItem.width),
            height: 22,
            angle: 0,
            text: `当前推荐 · ${primaryItem.variantId}`,
            fontSize: 14,
            fontFamily: 1,
            textAlign: 'left',
            verticalAlign: 'top',
            strokeColor: '#92400e',
            backgroundColor: 'transparent',
            fillStyle: 'solid',
            strokeWidth: 1,
            strokeStyle: 'solid',
            roundness: null,
            roughness: 0,
            opacity: 100,
            seed: Math.random(),
            version: 1,
            versionNonce: Math.random(),
            isDeleted: false,
            groupIds: [],
            boundElements: [],
            updated: Date.now(),
            frameId: null,
            index: null,
            locked: true,
            link: null,
            customData: {
              storyboardDecoration: 'primary-variant-label',
              storyboardId: primaryItem.storyboardId,
              shotId: primaryItem.shotId,
              variantId: primaryItem.variantId,
            },
          } as any,
        ]

    decorations.push(
      ...(convertToExcalidrawElements([
        ...groupElements,
        ...primaryElements,
      ]) as OrderedExcalidrawElement[])
    )
  })

  return decorations
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
    const videoLikeElement = element as { id?: string; type?: string; fileId?: string }
    if (videoLikeElement.type !== 'video') {
      continue
    }

    const fileId = videoLikeElement.fileId
    if (!fileId) {
      continue
    }

    persistedVideoElements[String(videoLikeElement.id || fileId)] = element
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
  const { excalidrawAPI, setExcalidrawAPI, mainImageFileId } = useCanvas()

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
        if (isStoryboardDecorationElement(element as { customData?: any })) {
          return false
        }
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
        appState: sanitizePersistedAppState(appState, {
          dropCanvasMetrics: true,
        }) as unknown as AppState,
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

    if (!CANVAS_ALLOWED_TOOLS.has(String(appState.activeTool?.type || 'selection'))) {
      queueMicrotask(() => {
        excalidrawAPI?.setActiveTool({ type: 'selection' })
      })
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
  const lastViewportSyncSignatureRef = useRef<string>(
    buildViewportSyncSignature(normalizeCanvasInitialData(initialData))
  )
  const shouldRefitOnInitialLoadRef = useRef<boolean>(
    shouldResetViewportOnLoad(normalizeCanvasInitialData(initialData))
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
        },
      })
    } else if (excalidrawAPI && theme === 'light') {
      // 恢复浅色背景
      excalidrawAPI.updateScene({
        appState: {
          viewBackgroundColor: '#ffffff',
        },
      })
    }
  }, [excalidrawAPI, theme])

  useEffect(() => {
    const persistedVideoState = extractPersistedVideoState(initialData)
    persistedVideoElementsRef.current = persistedVideoState.elements
    persistedVideoFilesRef.current = persistedVideoState.files
    shouldRefitOnInitialLoadRef.current = shouldResetViewportOnLoad(
      normalizeCanvasInitialData(initialData)
    )
  }, [initialData])

  useEffect(() => {
    if (!excalidrawAPI || !shouldRefitOnInitialLoadRef.current) {
      return
    }

    shouldRefitOnInitialLoadRef.current = false
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        try {
          excalidrawAPI.scrollToContent(undefined, {
            fitToContent: true,
            animate: false,
          })
          console.log('🖼️ Refit canvas viewport on initial load', {
            canvasId,
          })
        } catch (error) {
          console.warn('🖼️ Failed to refit canvas viewport on initial load', {
            canvasId,
            error,
          })
        }
      })
    })
  }, [canvasId, excalidrawAPI, initialData])

  useEffect(() => {
    if (!excalidrawAPI || !initialData) {
      return
    }

    const normalizedData = normalizeCanvasInitialData(initialData)
    const nextSignature = buildSceneSyncSignature(normalizedData)
    const nextViewportSignature = buildViewportSyncSignature(normalizedData)

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
      elements: [
        ...(normalizedData?.elements || []),
        ...buildStoryboardDecorations(normalizedData, mainImageFileId),
      ],
    })

    if (lastViewportSyncSignatureRef.current !== nextViewportSignature) {
      lastViewportSyncSignatureRef.current = nextViewportSignature
      requestAnimationFrame(() => {
        try {
          excalidrawAPI.scrollToContent(undefined, {
            fitToContent: true,
            animate: false,
          })
          console.log('🖼️ Refit canvas viewport after remote sync', {
            canvasId,
            viewportSignature: nextViewportSignature,
          })
        } catch (error) {
          console.warn('🖼️ Failed to refit canvas viewport after remote sync', {
            canvasId,
            error,
          })
        }
      })
    }
  }, [canvasId, excalidrawAPI, initialData, mainImageFileId])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable
      ) {
        return
      }

      const excalidrawRoot = document.querySelector('.excalidraw')
      if (!excalidrawRoot || !target || !excalidrawRoot.contains(target)) {
        return
      }

      const key = event.key.toLowerCase()
      const isModifierCombo = event.metaKey || event.ctrlKey

      if (
        key === 'delete' ||
        key === 'backspace' ||
        BLOCKED_CANVAS_SHORTCUTS.has(key) ||
        (isModifierCombo && ['c', 'v', 'x', 'z', 'y'].includes(key))
      ) {
        event.preventDefault()
        event.stopPropagation()
        excalidrawAPI?.setActiveTool({ type: 'selection' })
      }
    }

    document.addEventListener('keydown', handleKeyDown, true)
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [excalidrawAPI])

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

      const lockedImageElement = {
        ...imageElement,
        locked: true,
        groupIds: [],
        isDeleted: false,
        status: 'saved' as const,
      }

      excalidrawAPI.updateScene({
        elements: [...(currentElements || []), lockedImageElement],
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
            locked: true,
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
            src={link || ''}
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
    <div className={`${excalidrawClassName} w-full h-full min-h-0`}>
      <Excalidraw
        theme={customTheme as Theme}
        langCode={i18n.language}
        excalidrawAPI={(api) => {
          setExcalidrawAPI(api)
          api.setActiveTool({ type: 'selection' })
        }}
        onChange={handleChange}
        initialData={() => {
          const data = normalizeCanvasInitialData(initialData)
          console.log('👇initialData', data)
          if (!data) {
            return null
          }

          const dropViewport = shouldResetViewportOnLoad(data)
          const sanitizedAppState = sanitizePersistedAppState(data.appState, {
            dropViewport,
            dropCanvasMetrics: true,
          })

          return {
            ...data,
            appState: sanitizedAppState,
          }
        }}
        renderEmbeddable={renderEmbeddable}
        // Allow all URLs for embeddable content
        validateEmbeddable={(url: string) => {
          console.log('👇 Validating embeddable URL:', url)
          return true
        }}
        UIOptions={CANVAS_UI_OPTIONS}
        renderTopRightUI={() => null}
        viewModeEnabled={false}
        zenModeEnabled={false}
        handleKeyboardGlobally={true}
        onPointerUpdate={(payload) => {
          if (payload.button === 'down' && Math.random() < 0.05) {
            return
          }
        }}
      />
    </div>
  )
}

export { CanvasExcali }
export default CanvasExcali
