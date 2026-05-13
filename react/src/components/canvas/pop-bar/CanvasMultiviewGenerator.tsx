import { getCanvas } from '@/api/canvas'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import { useCanvas } from '@/contexts/canvas'
import { cn } from '@/lib/utils'
import { eventBus, TCanvasAddImagesToChatEvent } from '@/lib/event'
import { Camera, RotateCcw } from 'lucide-react'
import { memo, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

type CanvasMultiviewGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

type PresetDefinition = {
  id: string
  label: string
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
  positionClassName: string
}

const PRESETS: PresetDefinition[] = [
  {
    id: 'front',
    label: '正面',
    azimuth: 0,
    elevation: 0,
    framing: 'medium',
    positionClassName: 'left-1/2 top-3 -translate-x-1/2',
  },
  {
    id: 'left_front_45',
    label: '左前45°',
    azimuth: 45,
    elevation: 0,
    framing: 'medium',
    positionClassName: 'left-6 top-1/2 -translate-y-1/2',
  },
  {
    id: 'right_front_45',
    label: '右前45°',
    azimuth: -45,
    elevation: 0,
    framing: 'medium',
    positionClassName: 'right-6 top-1/2 -translate-y-1/2',
  },
  {
    id: 'high_angle',
    label: '俯拍',
    azimuth: 0,
    elevation: -25,
    framing: 'medium',
    positionClassName: 'left-1/2 top-14 -translate-x-[120px]',
  },
  {
    id: 'low_angle',
    label: '仰拍',
    azimuth: 0,
    elevation: 20,
    framing: 'medium',
    positionClassName: 'left-1/2 bottom-14 translate-x-[120px]',
  },
  {
    id: 'back',
    label: '背面',
    azimuth: 180,
    elevation: 0,
    framing: 'medium',
    positionClassName: 'left-1/2 bottom-3 -translate-x-1/2',
  },
]

const FRAMING_OPTIONS = [
  { value: 'close', label: '近景' },
  { value: 'medium', label: '中景' },
  { value: 'full', label: '全身' },
  { value: 'wide', label: '远景' },
] as const

type PreviewCard = {
  label: string
  url: string
}

const CanvasMultiviewGenerator = ({
  selectedImages,
}: CanvasMultiviewGeneratorProps) => {
  const { canvasId } = useCanvas()
  const [open, setOpen] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [refinePrompt, setRefinePrompt] = useState('')
  const [presetName, setPresetName] = useState('left_front_45')
  const [azimuth, setAzimuth] = useState(45)
  const [elevation, setElevation] = useState(0)
  const [framing, setFraming] = useState<'close' | 'medium' | 'full' | 'wide'>(
    'medium'
  )
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [previewCards, setPreviewCards] = useState<PreviewCard[]>([])
  const [previewRefreshToken, setPreviewRefreshToken] = useState(0)

  const selectedImage = selectedImages[0]
  const previewUrl = useMemo(
    () => selectedImage?.base64 || '',
    [selectedImage?.base64]
  )

  const applyPreset = (preset: PresetDefinition) => {
    setPresetName(preset.id)
    setAzimuth(preset.azimuth)
    setElevation(preset.elevation)
    setFraming(preset.framing)
  }

  const handleReset = () => {
    const defaultPreset = PRESETS.find((preset) => preset.id === 'left_front_45')
    if (defaultPreset) {
      applyPreset(defaultPreset)
    }
    setPrompt('')
    setRefinePrompt('')
    setAspectRatio('16:9')
  }

  const handleGenerateMultiview = (options?: {
    previewOnly?: boolean
    replaceSource?: boolean
    mode?: 'multiview' | 'refinement'
  }) => {
    if (!selectedImage) {
      toast.warning('请先选中一张分镜图')
      return
    }

    eventBus.emit('Canvas::GenerateMultiview', {
      selectedImage,
      prompt:
        options?.mode === 'refinement' ? refinePrompt.trim() : prompt.trim(),
      presetName,
      azimuth,
      elevation,
      framing,
      aspectRatio,
      previewOnly: options?.previewOnly ?? false,
      replaceSource: options?.replaceSource ?? false,
      mode: options?.mode ?? 'multiview',
    })

    if (!options?.previewOnly) {
      setOpen(false)
    }
  }

  useEffect(() => {
    const loadPreviewCards = async () => {
      if (!open || !selectedImage || !canvasId) {
        return
      }

      try {
        const selectedCanvasFileId = String(
          selectedImage.canvasFileId || selectedImage.fileId || ''
        ).trim()
        const canvas = await getCanvas(canvasId)
        const files = canvas?.data?.files || {}
        const selectedCanvasFile = files[selectedCanvasFileId] as
          | { dataURL?: string; storyboardMeta?: Record<string, any>; created?: number }
          | undefined
        const selectedStoryboardMeta =
          selectedCanvasFile?.storyboardMeta &&
          typeof selectedCanvasFile.storyboardMeta === 'object'
            ? selectedCanvasFile.storyboardMeta
            : {}

        const sourceMainImageFileId = String(
          selectedStoryboardMeta?.source_main_image_file_id || selectedCanvasFileId
        )
        const shotId = String(selectedStoryboardMeta?.shot_id || '')
        const shotFamilyId = String(selectedStoryboardMeta?.shot_family_id || '')

        const cards: PreviewCard[] = [
          {
            label: '当前图',
            url:
              previewUrl ||
              String(selectedCanvasFile?.dataURL || `/api/file/${selectedImage.fileId}`),
          },
        ]

        const mainImageFile = files[sourceMainImageFileId] as
          | { dataURL?: string }
          | undefined
        const mainImageUrl = String(mainImageFile?.dataURL || '')
        if (mainImageUrl) {
          cards.unshift({
            label: '主图参考',
            url: mainImageUrl,
          })
        }

        if (shotId || shotFamilyId) {
          const recentCandidateEntry = Object.entries(files)
            .filter(([fileId, file]) => {
              if (fileId === selectedCanvasFileId) {
                return false
              }
              if (!file || typeof file !== 'object') {
                return false
              }
              const meta = (file as { storyboardMeta?: Record<string, any> }).storyboardMeta
              if (!meta) {
                return false
              }
              if (shotFamilyId) {
                return String(meta.shot_family_id || '') === shotFamilyId
              }
              return String(meta.shot_id || '') === shotId
            })
            .sort((a, b) => {
              const aCreated = Number((a[1] as { created?: number }).created || 0)
              const bCreated = Number((b[1] as { created?: number }).created || 0)
              return bCreated - aCreated
            })[0]

          const recentCandidateUrl = String(
            (recentCandidateEntry?.[1] as { dataURL?: string } | undefined)?.dataURL || ''
          )
          if (recentCandidateUrl) {
            cards.push({
              label: shotFamilyId ? '这一组最近结果' : '最近结果',
              url: recentCandidateUrl,
            })
          }
        }

        setPreviewCards(cards)
      } catch (error) {
        console.error('Failed to load multiview preview cards:', error)
        setPreviewCards(
          previewUrl
            ? [
                {
                  label: '当前图',
                  url: previewUrl,
                },
              ]
            : []
        )
      }
    }

    loadPreviewCards()
  }, [canvasId, open, previewRefreshToken, previewUrl, selectedImage])

  useEffect(() => {
    const handleRefresh = (event: Event) => {
      const payload = (event as CustomEvent<{ canvasId?: string; reason?: string }>)
        .detail
      if (!open) {
        return
      }
      if (payload?.canvasId && payload.canvasId !== canvasId) {
        return
      }
      setPreviewRefreshToken((prev) => prev + 1)
    }

    window.addEventListener('app:refresh-canvas', handleRefresh as EventListener)
    return () => {
      window.removeEventListener(
        'app:refresh-canvas',
        handleRefresh as EventListener
      )
    }
  }, [canvasId, open])

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        生成更多角度
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-5xl">
          <DialogHeader>
            <DialogTitle>生成更多角度</DialogTitle>
            <DialogDescription>
              基于当前这张图生成更多角度或做单张优化。默认是新增结果，不会直接覆盖当前图片。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 md:grid-cols-3">
            {previewCards.length > 0 ? (
              previewCards.map((card) => (
                <div key={card.label} className="rounded-xl border bg-muted/20 p-3">
                  <div className="mb-2 text-sm font-medium text-foreground">
                    {card.label}
                  </div>
                  <div className="overflow-hidden rounded-lg border bg-background">
                    <img
                      src={card.url}
                      alt={card.label}
                      className="aspect-video h-full w-full object-cover"
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border bg-muted/20 p-3 text-sm text-muted-foreground md:col-span-3">
                暂无可展示的主图参考或最近候选。
              </div>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
            <div className="rounded-2xl border bg-gradient-to-br from-slate-50 via-white to-slate-100 p-4">
              <div className="mb-3 text-sm font-medium text-foreground">
                镜头控制球
              </div>
              <div className="relative mx-auto flex aspect-square max-w-[360px] items-center justify-center rounded-full border border-slate-300 bg-[radial-gradient(circle_at_center,_rgba(255,255,255,1),_rgba(226,232,240,0.8)_65%,_rgba(203,213,225,0.7))] shadow-inner">
                {PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset)}
                    className={cn(
                      'absolute rounded-full border px-3 py-1 text-xs shadow-sm transition hover:scale-105',
                      preset.positionClassName,
                      presetName === preset.id
                        ? 'border-blue-500 bg-blue-500 text-white'
                        : 'border-slate-300 bg-white/90 text-slate-700'
                    )}
                  >
                    {preset.label}
                  </button>
                ))}

                <div className="flex h-40 w-40 items-center justify-center overflow-hidden rounded-full border border-white/70 bg-slate-200 shadow-lg">
                  {previewUrl ? (
                    <img
                      src={previewUrl}
                      alt="Selected storyboard frame"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="text-sm text-muted-foreground">暂无预览</div>
                  )}
                </div>

                <div className="absolute bottom-10 rounded-full border border-slate-300 bg-white/90 px-3 py-1 text-xs text-slate-700 shadow-sm">
                  <span className="inline-flex items-center gap-1">
                    <Camera className="h-3.5 w-3.5" />
                    相机视角
                  </span>
                </div>
              </div>

              <div className="mt-4 rounded-xl border bg-white/80 p-3 text-sm text-muted-foreground">
                当前参数：水平环绕 {azimuth}°，垂直俯仰 {elevation}°，景别{' '}
                {FRAMING_OPTIONS.find((item) => item.value === framing)?.label}
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <div className="text-sm font-medium">中文微调说明</div>
                <Textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="例如：镜头更像广告 hero 角度，主体更稳，背景尽量延续。"
                  className="min-h-24"
                />
              </div>

              <div className="space-y-2 rounded-xl border border-dashed p-3">
                <div className="text-sm font-medium">单张优化</div>
                <div className="text-xs text-muted-foreground">
                  保持当前人物、场景和构图逻辑，只优化这一张图本身。
                </div>
                <Textarea
                  value={refinePrompt}
                  onChange={(event) => setRefinePrompt(event.target.value)}
                  placeholder="例如：让人物表情更自然，手部动作更明确，保持同一场景与服装。"
                  className="min-h-24"
                />
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium">预设视角</div>
                <div className="flex flex-wrap gap-2">
                  {PRESETS.map((preset) => (
                    <Button
                      key={preset.id}
                      type="button"
                      variant={presetName === preset.id ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => applyPreset(preset)}
                    >
                      {preset.label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-3 rounded-xl border p-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">水平环绕</span>
                    <span className="text-muted-foreground">{azimuth}°</span>
                  </div>
                  <Slider
                    min={-180}
                    max={180}
                    step={5}
                    value={[azimuth]}
                    onValueChange={(value) => {
                      setPresetName('custom')
                      setAzimuth(value[0] || 0)
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">垂直俯仰</span>
                    <span className="text-muted-foreground">{elevation}°</span>
                  </div>
                  <Slider
                    min={-45}
                    max={45}
                    step={5}
                    value={[elevation]}
                    onValueChange={(value) => {
                      setPresetName('custom')
                      setElevation(value[0] || 0)
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">景别</div>
                  <div className="grid grid-cols-4 gap-2">
                    {FRAMING_OPTIONS.map((option) => (
                      <Button
                        key={option.value}
                        type="button"
                        variant={framing === option.value ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => {
                          setPresetName('custom')
                          setFraming(option.value)
                        }}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">输出比例</div>
                  <div className="flex flex-wrap gap-2">
                    {['16:9', '9:16', '1:1', '4:5'].map((ratio) => (
                      <Button
                        key={ratio}
                        type="button"
                        variant={aspectRatio === ratio ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setAspectRatio(ratio)}
                      >
                        {ratio}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleReset}>
              <RotateCcw className="mr-2 h-4 w-4" />
              重置参数
            </Button>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button
              variant="outline"
              onClick={() => handleGenerateMultiview({ previewOnly: true })}
            >
              生成预览
            </Button>
            <Button
              variant="outline"
              onClick={() => handleGenerateMultiview({ replaceSource: true })}
            >
              直接替换当前图
            </Button>
            <Button onClick={() => handleGenerateMultiview()}>生成更多角度</Button>
            <Button
              variant="secondary"
              onClick={() =>
                handleGenerateMultiview({
                  mode: 'refinement',
                })
              }
            >
              单张优化
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(CanvasMultiviewGenerator)
