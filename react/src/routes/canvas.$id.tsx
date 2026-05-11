import { getCanvas, renameCanvas } from '@/api/canvas'
import CanvasExcali from '@/components/canvas/CanvasExcali'
import CanvasHeader from '@/components/canvas/CanvasHeader'
import CanvasMenu from '@/components/canvas/menu'
import CanvasPopbarWrapper from '@/components/canvas/pop-bar'
// VideoCanvasOverlay removed - using native Excalidraw embeddable elements instead
import ChatInterface from '@/components/chat/Chat'
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable'
import { CanvasProvider } from '@/contexts/canvas'
import { Session } from '@/types/types'
import { createFileRoute, useParams, useSearch } from '@tanstack/react-router'
import { Loader2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

export const Route = createFileRoute('/canvas/$id')({
  component: Canvas,
})

function Canvas() {
  const { id } = useParams({ from: '/canvas/$id' })
  const [canvas, setCanvas] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [canvasName, setCanvasName] = useState('')
  const [sessionList, setSessionList] = useState<Session[]>([])
  // initialVideos removed - using native Excalidraw embeddable elements instead
  const search = useSearch({ from: '/canvas/$id' }) as {
    sessionId: string
  }
  const searchSessionId = search?.sessionId || ''
  const fetchCanvas = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = !!options?.silent
      try {
        if (!silent) {
          setIsLoading(true)
        }
        setError(null)
        const data = await getCanvas(id)
        setCanvas(data)
        setCanvasName(data.name)
        setSessionList(data.sessions)
        console.log('🖼️ Canvas refreshed', {
          canvasId: id,
          silent,
          elementCount: data?.data?.elements?.length ?? 0,
          fileCount: Object.keys(data?.data?.files || {}).length,
        })
      } catch (err) {
        setError(
          err instanceof Error ? err : new Error('Failed to fetch canvas data')
        )
        console.error('Failed to fetch canvas data:', err)
      } finally {
        if (!silent) {
          setIsLoading(false)
        }
      }
    },
    [id]
  )

  useEffect(() => {
    let mounted = true
    if (mounted) {
      fetchCanvas()
    }

    return () => {
      mounted = false
    }
  }, [fetchCanvas])

  useEffect(() => {
    const handleRefresh = (event: Event) => {
      const payload = (event as CustomEvent<{ canvasId?: string; reason?: string }>)
        .detail
      if (payload?.canvasId && payload.canvasId !== id) {
        return
      }
      console.log('🖼️ Canvas refresh requested', {
        canvasId: id,
        reason: payload?.reason || 'unknown',
      })
      fetchCanvas({ silent: true })
    }

    window.addEventListener('jaaz:refresh-canvas', handleRefresh as EventListener)
    return () => {
      window.removeEventListener(
        'jaaz:refresh-canvas',
        handleRefresh as EventListener
      )
    }
  }, [fetchCanvas, id])

  const handleNameSave = async () => {
    await renameCanvas(id, canvasName)
  }

  return (
    <CanvasProvider canvasId={id}>
      <div className='flex flex-col w-screen h-screen'>
        <CanvasHeader
          canvasName={canvasName}
          canvasId={id}
          onNameChange={setCanvasName}
          onNameSave={handleNameSave}
        />
        <ResizablePanelGroup
          direction='horizontal'
          className='w-screen h-screen'
          autoSaveId='jaaz-chat-panel'
        >
          <ResizablePanel className='relative' defaultSize={75}>
            <div className='w-full h-full'>
              {isLoading ? (
                <div className='flex-1 flex-grow px-4 bg-accent w-[24%] absolute right-0'>
                  <div className='flex items-center justify-center h-full'>
                    <Loader2 className='w-4 h-4 animate-spin' />
                  </div>
                </div>
              ) : (
                <div className='relative w-full h-full'>
                  <CanvasExcali canvasId={id} initialData={canvas?.data} />
                  <CanvasMenu />
                  <CanvasPopbarWrapper />
                </div>
              )}
            </div>
          </ResizablePanel>

          <ResizableHandle />

          <ResizablePanel defaultSize={25}>
            <div className='flex-1 flex-grow bg-accent/50 w-full'>
              <ChatInterface
                canvasId={id}
                sessionList={sessionList}
                setSessionList={setSessionList}
                sessionId={searchSessionId}
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </CanvasProvider>
  )
}
