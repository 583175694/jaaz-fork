import { ExcalidrawImperativeAPI } from '@excalidraw/excalidraw/types'
import { create } from 'zustand'
import {
  ContinuityAsset,
  StoryboardPlanAsset,
  VideoBriefAsset,
} from '@/types/types'

const MAIN_IMAGE_STORAGE_KEY = 'main_image_file_id_by_canvas'

const readMainImageMap = (): Record<string, string> => {
  if (typeof window === 'undefined') {
    return {}
  }

  try {
    const raw = localStorage.getItem(MAIN_IMAGE_STORAGE_KEY)
    if (!raw) {
      return {}
    }

    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    console.warn('Failed to parse main image map from localStorage', error)
    return {}
  }
}

const writeMainImageMap = (nextMap: Record<string, string>) => {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.setItem(MAIN_IMAGE_STORAGE_KEY, JSON.stringify(nextMap))
}

const migrateLegacyMainImage = (canvasId: string) => {
  if (typeof window === 'undefined' || !canvasId) {
    return ''
  }

  const currentMap = readMainImageMap()
  const existingValue = currentMap[canvasId]
  if (existingValue) {
    return existingValue
  }

  const legacyValue = localStorage.getItem('main_image_file_id') || ''
  if (legacyValue) {
    currentMap[canvasId] = legacyValue
    writeMainImageMap(currentMap)
    localStorage.removeItem('main_image_file_id')
    return legacyValue
  }

  return ''
}

type CanvasStore = {
  canvasId: string
  mainImageFileId: string
  currentContinuityId: string
  continuityAsset: ContinuityAsset | null
  storyboardPlan: StoryboardPlanAsset | null
  currentVideoBrief: VideoBriefAsset | null
  excalidrawAPI: ExcalidrawImperativeAPI | null

  setCanvasId: (canvasId: string) => void
  setMainImageFileId: (fileId: string) => void
  setCurrentContinuity: (asset: ContinuityAsset | null) => void
  setStoryboardPlan: (plan: StoryboardPlanAsset | null) => void
  setCurrentVideoBrief: (brief: VideoBriefAsset | null) => void
  setExcalidrawAPI: (excalidrawAPI: ExcalidrawImperativeAPI) => void
}

const useCanvasStore = create<CanvasStore>((set, get) => ({
  canvasId: typeof window !== 'undefined' ? localStorage.getItem('canvas_id') || '' : '',
  mainImageFileId:
    typeof window !== 'undefined'
      ? migrateLegacyMainImage(localStorage.getItem('canvas_id') || '')
      : '',
  currentContinuityId: '',
  continuityAsset: null,
  storyboardPlan: null,
  currentVideoBrief: null,
  excalidrawAPI: null,

  setCanvasId: (canvasId) => {
    localStorage.setItem('canvas_id', canvasId)
    const nextMainImageFileId = migrateLegacyMainImage(canvasId)
    set({
      canvasId,
      mainImageFileId: nextMainImageFileId,
    })
  },
  setMainImageFileId: (mainImageFileId) => {
    const currentCanvasId = get().canvasId
    const currentMap = readMainImageMap()

    if (currentCanvasId) {
      currentMap[currentCanvasId] = mainImageFileId
      writeMainImageMap(currentMap)
    }

    set({ mainImageFileId })
  },
  setCurrentContinuity: (continuityAsset) =>
    set({
      continuityAsset,
      currentContinuityId: continuityAsset?.continuity_id || '',
      mainImageFileId:
        continuityAsset?.source_main_image_file_id || get().mainImageFileId,
    }),
  setStoryboardPlan: (storyboardPlan) => set({ storyboardPlan }),
  setCurrentVideoBrief: (currentVideoBrief) => set({ currentVideoBrief }),
  setExcalidrawAPI: (excalidrawAPI) => set({ excalidrawAPI }),
}))

export default useCanvasStore
