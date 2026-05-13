import { previewDirectVideoPrompt } from '@/api/video'
import { useCanvas } from '@/contexts/canvas'
import { useConfigs } from '@/contexts/configs'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { eventBus, TCanvasAddImagesToChatEvent } from '@/lib/event'
import { ArrowLeftRight, Check, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { memo, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'

type CanvasVideoGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const MAX_REFERENCE_IMAGES = 2

const getConfiguredVideoModel = async () => {
  const response = await fetch('/api/config')
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`)
  }
  const config = await response.json()
  return String(config?.apipodvideo?.model_name || '')
}

const CanvasVideoGenerator = ({ selectedImages }: CanvasVideoGeneratorProps) => {
  const { t } = useTranslation()
  const { canvasId } = useCanvas()
  const { textModel } = useConfigs()
  const [open, setOpen] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [userPrompt, setUserPrompt] = useState('')
  const [finalPrompt, setFinalPrompt] = useState('')
  const [isBuildingPrompt, setIsBuildingPrompt] = useState(false)
  const [duration, setDuration] = useState('6')
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [resolution, setResolution] = useState('1080p')
  const [orderedImages, setOrderedImages] = useState<TCanvasAddImagesToChatEvent>([])

  const normalizedSelectedImages = useMemo(
    () => selectedImages.slice(0, MAX_REFERENCE_IMAGES),
    [selectedImages]
  )

  useEffect(() => {
    if (!open) {
      return
    }
    setOrderedImages(normalizedSelectedImages)
  }, [normalizedSelectedImages, open])

  const invalidateFinalPrompt = () => {
    setFinalPrompt('')
  }

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setUserPrompt('')
      setFinalPrompt('')
      setShowAdvanced(false)
      setOrderedImages([])
    }
  }

  const handleSwapImages = () => {
    if (orderedImages.length < 2) {
      return
    }
    setOrderedImages([orderedImages[1], orderedImages[0]])
    invalidateFinalPrompt()
  }

  const handleBuildPrompt = async () => {
    if (!canvasId) {
      toast.error('当前画布信息缺失，暂时无法生成提示词')
      return
    }
    const trimmedUserPrompt = userPrompt.trim()
    if (!trimmedUserPrompt) {
      toast.warning('请先输入视频需求')
      return
    }

    if (selectedImages.length === 0) {
      toast.warning('请先选中一张图片')
      return
    }

    if (selectedImages.length > MAX_REFERENCE_IMAGES) {
      toast.info('Veo 3.1 最多使用 2 张参考图，当前仅取前 2 张')
    }

    try {
      const configuredModelName = await getConfiguredVideoModel()
      if (
        normalizedSelectedImages.length > 1 &&
        configuredModelName &&
        !['veo3-1-fast', 'veo3-1-quality'].includes(configuredModelName)
      ) {
        toast.error('当前视频模型不支持多图参考', {
          description: '当前内置视频能力仅支持单图参考，请改为只选择 1 张图片后再生成。',
        })
        return
      }
    } catch (error) {
      console.error('Failed to inspect video model config:', error)
    }

    const imagesForPrompt = orderedImages.length > 0 ? orderedImages : normalizedSelectedImages
    const startFrame = imagesForPrompt[0]
    const endFrame = imagesForPrompt.length > 1 ? imagesForPrompt[1] : imagesForPrompt[0]

    setIsBuildingPrompt(true)
    try {
      const result = await previewDirectVideoPrompt({
        canvasId,
        textModel,
        fileIds: imagesForPrompt.map((image) => image.fileId),
        prompt: trimmedUserPrompt,
        duration: Number(duration),
        aspectRatio,
        resolution,
        selectionMode: 'start_end_frames',
        startFrameFileId: startFrame?.fileId,
        endFrameFileId: endFrame?.fileId,
      })
      const nextPrompt = String(result?.prompt || '').trim()
      if (!nextPrompt) {
        throw new Error('模型没有返回可用的视频提示词')
      }
      setFinalPrompt(nextPrompt)
    } catch (error) {
      console.error('Failed to build video prompt:', error)
      toast.error('生成提示词失败', {
        description: String(error),
      })
    } finally {
      setIsBuildingPrompt(false)
    }
  }

  const handleGenerateVideo = () => {
    const trimmedUserPrompt = userPrompt.trim()
    const trimmedFinalPrompt = finalPrompt.trim()
    if (!trimmedUserPrompt) {
      toast.warning('请先输入视频需求')
      return
    }
    if (!trimmedFinalPrompt) {
      toast.warning('请先优化并确认最终提示词')
      return
    }

    eventBus.emit('Canvas::GenerateVideo', {
      selectedImages: orderedImages.length > 0 ? orderedImages : normalizedSelectedImages,
      userPrompt: trimmedUserPrompt,
      finalPrompt: trimmedFinalPrompt,
      duration: Number(duration),
      aspectRatio,
      resolution,
      selectionMode: 'start_end_frames',
    })

    setOpen(false)
    setUserPrompt('')
    setFinalPrompt('')
    setShowAdvanced(false)
    setOrderedImages([])
  }

  return (
    <>
      <Button variant='ghost' size='sm' onClick={() => setOpen(true)}>
        {t('canvas:popbar.generateVideo')}
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className='max-w-4xl overflow-hidden p-0'>
          <div className='flex max-h-[calc(100vh-2rem)] flex-col'>
          <DialogHeader className='shrink-0 border-b px-6 py-5'>
            <DialogTitle>生成视频</DialogTitle>
            <DialogDescription>
              先填写视频需求，再由系统优化为可生成的视频提示词。
            </DialogDescription>
          </DialogHeader>

          <div className='flex-1 overflow-y-auto px-6 py-5'>
          <div className='space-y-5'>
            <div
              className={cn(
                'grid gap-4',
                orderedImages.length > 1 ? 'md:grid-cols-2' : 'md:grid-cols-1'
              )}
            >
              {(orderedImages.length > 0 ? orderedImages : normalizedSelectedImages).map(
                (image, index) => (
                  <div
                    key={`${image.fileId}-${index}`}
                    className='rounded-xl border bg-muted/20 p-3'
                  >
                    <div className='mb-3 flex items-center justify-between gap-3'>
                      <div className='text-sm font-medium text-foreground'>
                        {orderedImages.length > 1
                          ? index === 0
                            ? '首帧参考'
                            : '尾帧参考'
                          : '参考画面'}
                      </div>
                      {orderedImages.length > 1 && (
                        <div className='text-xs text-muted-foreground'>
                          {index === 0 ? '将从这张图开始' : '将过渡到这张图结束'}
                        </div>
                      )}
                    </div>
                    <div className='overflow-hidden rounded-lg border bg-background'>
                      {image.base64 ? (
                        <img
                          src={image.base64}
                          alt={`Selected frame ${index + 1}`}
                          className='aspect-video h-full w-full object-cover'
                        />
                      ) : (
                        <div className='flex aspect-video items-center justify-center text-sm text-muted-foreground'>
                          暂无预览
                        </div>
                      )}
                    </div>
                  </div>
                )
              )}
            </div>

            {orderedImages.length > 1 && (
              <div className='flex justify-center'>
                <Button type='button' variant='outline' onClick={handleSwapImages}>
                  <ArrowLeftRight className='mr-2 h-4 w-4' />
                  交换首尾顺序
                </Button>
              </div>
            )}

            <div className='space-y-4'>
              <div className='rounded-xl border bg-muted/20 p-4'>
                <div className='mb-2 flex items-center gap-2 text-sm font-medium text-foreground'>
                  <Sparkles className='h-4 w-4' />
                  视频需求
                </div>
                <Textarea
                  value={userPrompt}
                  onChange={(event) => {
                    setUserPrompt(event.target.value)
                    invalidateFinalPrompt()
                  }}
                  placeholder='先描述你想生成的视频内容、镜头运动、风格、节奏和重点。'
                  className='min-h-32'
                />
              </div>

              <div className='rounded-xl border bg-muted/20 p-4'>
                <div className='mb-2 flex items-center gap-2 text-sm font-medium text-foreground'>
                  <Sparkles className='h-4 w-4' />
                  专业优化后的提示词
                </div>
                <Textarea
                  value={finalPrompt}
                  onChange={(event) => setFinalPrompt(event.target.value)}
                  placeholder={
                    isBuildingPrompt ? '正在优化提示词...' : '点击“优化提示词”后会在这里生成专业提示词'
                  }
                  className='min-h-72'
                />
              </div>
            </div>
          </div>

          <div className='rounded-xl border'>
            <button
              type='button'
              onClick={() => setShowAdvanced((prev) => !prev)}
              className='flex w-full items-center justify-between px-4 py-3 text-left'
            >
              <div>
                <div className='text-sm font-medium'>高级设置</div>
                <div className='text-xs text-muted-foreground'>
                  默认设置已经可直接使用，需要时再展开调整。
                </div>
              </div>
              {showAdvanced ? (
                <ChevronUp className='h-4 w-4 text-muted-foreground' />
              ) : (
                <ChevronDown className='h-4 w-4 text-muted-foreground' />
              )}
            </button>

            {showAdvanced && (
              <div className='grid gap-4 border-t px-4 py-4 md:grid-cols-3'>
                <div className='space-y-2'>
                  <div className='text-sm font-medium'>时长</div>
                  <Select
                    value={duration}
                    onValueChange={(value) => {
                      setDuration(value)
                      invalidateFinalPrompt()
                    }}
                  >
                    <SelectTrigger className='w-full'>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='5'>5 秒</SelectItem>
                      <SelectItem value='6'>6 秒</SelectItem>
                      <SelectItem value='8'>8 秒</SelectItem>
                      <SelectItem value='10'>10 秒</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className='space-y-2'>
                  <div className='text-sm font-medium'>比例</div>
                  <Select
                    value={aspectRatio}
                    onValueChange={(value) => {
                      setAspectRatio(value)
                      invalidateFinalPrompt()
                    }}
                  >
                    <SelectTrigger className='w-full'>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='16:9'>16:9</SelectItem>
                      <SelectItem value='9:16'>9:16</SelectItem>
                      <SelectItem value='1:1'>1:1</SelectItem>
                      <SelectItem value='4:5'>4:5</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className='space-y-2'>
                  <div className='text-sm font-medium'>分辨率</div>
                  <Select
                    value={resolution}
                    onValueChange={(value) => {
                      setResolution(value)
                      invalidateFinalPrompt()
                    }}
                  >
                    <SelectTrigger className='w-full'>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='720p'>720p</SelectItem>
                      <SelectItem value='1080p'>1080p</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>
          </div>

          <DialogFooter className='shrink-0 border-t px-6 py-4'>
            <Button variant='outline' onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={handleBuildPrompt} disabled={isBuildingPrompt}>
              {isBuildingPrompt ? '正在优化提示词...' : '优化提示词'}
            </Button>
            <Button
              onClick={handleGenerateVideo}
              disabled={isBuildingPrompt || !userPrompt.trim() || !finalPrompt.trim()}
            >
              <Check className='mr-2 h-4 w-4' />
              开始生成视频
            </Button>
          </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(CanvasVideoGenerator)
