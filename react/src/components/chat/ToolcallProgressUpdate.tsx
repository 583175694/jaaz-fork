import { eventBus } from '@/lib/event'
import { TEvents } from '@/lib/event'
import { useEffect } from 'react'
import Spinner from '@/components/ui/Spinner'
import { useState } from 'react'

const normalizeProgressCopy = (progress: string) => {
  const trimmed = String(progress || '').trim()
  if (!trimmed) {
    return ''
  }

  if (trimmed.includes('video')) {
    return '正在生成视频'
  }
  if (trimmed.includes('storyboard')) {
    return '正在生成分镜'
  }
  if (trimmed.includes('image')) {
    return '正在生成图片'
  }
  if (trimmed.includes('prompt')) {
    return '正在优化提示词'
  }

  return trimmed
}

export default function ToolcallProgressUpdate({
  sessionId,
}: {
  sessionId: string
}) {
  const [progress, setProgress] = useState('')

  useEffect(() => {
    const handleToolCallProgress = (
      data: TEvents['Socket::Session::ToolCallProgress']
    ) => {
      if (data.session_id === sessionId) {
        setProgress(data.update)
      }
    }

    eventBus.on('Socket::Session::ToolCallProgress', handleToolCallProgress)
    return () => {
      eventBus.off('Socket::Session::ToolCallProgress', handleToolCallProgress)
    }
  }, [sessionId])
  if (!progress) return null
  return (
    <div className="flex items-center gap-2 rounded-full border border-border/70 bg-background/80 px-3 py-2 text-sm text-muted-foreground backdrop-blur-sm">
      <Spinner size={4} />
      <span>{normalizeProgressCopy(progress)}</span>
    </div>
  )
}
