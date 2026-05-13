import useCanvasStore from '@/stores/canvas'
import { createContext, useContext, useEffect } from 'react'
import {
  getCurrentContinuity,
  getCurrentMainImage,
  getCurrentStoryboardPlan,
  getCurrentVideoBrief,
} from '@/api/canvas'

export const CanvasContext = createContext<{
  canvasStore: typeof useCanvasStore
} | null>(null)

export const CanvasProvider = ({
  children,
  canvasId,
}: {
  children: React.ReactNode
  canvasId?: string
}) => {
  const canvasStore = useCanvasStore

  const syncProductionState = async (
    targetCanvasId: string,
    options?: { silent?: boolean }
  ) => {
    try {
      const [mainImageResp, continuityResp, storyboardResp, videoBriefResp] =
        await Promise.all([
          getCurrentMainImage(targetCanvasId),
          getCurrentContinuity(targetCanvasId),
          getCurrentStoryboardPlan(targetCanvasId),
          getCurrentVideoBrief(targetCanvasId),
        ])
      canvasStore.getState().setMainImageFileId(mainImageResp?.file_id || '')
      canvasStore.getState().setCurrentContinuity(continuityResp?.item || null)
      canvasStore.getState().setStoryboardPlan(storyboardResp?.item || null)
      canvasStore.getState().setCurrentVideoBrief(videoBriefResp?.item || null)
      return true
    } catch (error) {
      if (!options?.silent) {
        console.warn('Failed to sync canvas production state', {
          canvasId: targetCanvasId,
          error,
        })
      }
      return false
    }
  }

  useEffect(() => {
    if (canvasId) {
      canvasStore.getState().setCanvasId(canvasId)
    }
  }, [canvasId, canvasStore])

  useEffect(() => {
    if (!canvasId) {
      return
    }

    void syncProductionState(canvasId, { silent: false })
  }, [canvasId, canvasStore])

  useEffect(() => {
    if (!canvasId) {
      return
    }

    const handleRefresh = async (event: Event) => {
      const payload = (event as CustomEvent<{ canvasId?: string; reason?: string }>)
        .detail
      if (payload?.canvasId && payload.canvasId !== canvasId) {
        return
      }

      await syncProductionState(canvasId, { silent: false })
    }

    window.addEventListener('app:refresh-canvas', handleRefresh as EventListener)
    return () => {
      window.removeEventListener(
        'app:refresh-canvas',
        handleRefresh as EventListener
      )
    }
  }, [canvasId, canvasStore])

  return (
    <CanvasContext.Provider value={{ canvasStore }}>
      {children}
    </CanvasContext.Provider>
  )
}

export const useCanvas = () => {
  const context = useContext(CanvasContext)
  if (!context) {
    throw new Error('useCanvas must be used within a CanvasProvider')
  }
  return context.canvasStore()
}
