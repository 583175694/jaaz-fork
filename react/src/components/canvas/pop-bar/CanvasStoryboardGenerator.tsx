import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useCanvas } from '@/contexts/canvas'
import { eventBus, TCanvasAddImagesToChatEvent } from '@/lib/event'
import { DEFAULT_IMAGE_MODEL, IMAGE_MODEL_OPTIONS, ImageModelOption } from '@/lib/imageModels'
import { Check, Sparkles } from 'lucide-react'
import { memo, useMemo, useState } from 'react'
import { toast } from 'sonner'

type CanvasStoryboardGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const buildStoryboardPrompt = (params: {
  userPrompt: string
  shotCount: number
  aspectRatio: string
}) => {
  const promptParts = [
    '基于当前选中的参考图生成一组可直接用于短视频创作的商业分镜。',
    '保持同一个主体、服装、产品形态、场景空间和光线逻辑连续，画面风格统一，适合连续剪辑。',
    `输出 ${params.shotCount} 张分镜图，按镜头推进自然展开，包含开场、推进、重点和收束。`,
    `画面比例为 ${params.aspectRatio}。`,
    '每一张图都要有明确镜头差异，例如景别、机位、动作推进或视线变化，但不要跳到新的场景或新的角色设定。',
  ]

  const normalizedUserPrompt = params.userPrompt.trim()
  if (normalizedUserPrompt) {
    promptParts.push(`额外要求：${normalizedUserPrompt}`)
  }

  return promptParts.join('\n')
}

const CanvasStoryboardGenerator = ({
  selectedImages,
}: CanvasStoryboardGeneratorProps) => {
  const { mainImageFileId } = useCanvas()
  const [open, setOpen] = useState(false)
  const [userPrompt, setUserPrompt] = useState('')
  const [finalPrompt, setFinalPrompt] = useState('')
  const [step, setStep] = useState<'form' | 'confirm'>('form')
  const [shotCount, setShotCount] = useState('4')
  const [aspectRatio, setAspectRatio] = useState('16:9')
  const [imageModel, setImageModel] =
    useState<ImageModelOption>(DEFAULT_IMAGE_MODEL)

  const selectedImage = selectedImages[0]
  const previewUrl = useMemo(
    () => selectedImage?.base64 || '',
    [selectedImage?.base64]
  )

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (!nextOpen) {
      setStep('form')
      setFinalPrompt('')
      setImageModel(DEFAULT_IMAGE_MODEL)
    }
  }

  const handleBuildPrompt = () => {
    if (!selectedImage) {
      toast.warning('请先选中一张图片')
      return
    }

    const nextPrompt = buildStoryboardPrompt({
      userPrompt,
      shotCount: Number(shotCount),
      aspectRatio,
    })

    setFinalPrompt(nextPrompt)
    setStep('confirm')
  }

  const handleGenerateStoryboard = () => {
    if (!selectedImage) {
      toast.warning('请先选中一张图片')
      return
    }

    const trimmedFinalPrompt = finalPrompt.trim()
    if (!trimmedFinalPrompt) {
      toast.warning('请先确认最终提示词')
      return
    }

    eventBus.emit('Canvas::GenerateStoryboard', {
      selectedImage,
      mainImageFileId:
        mainImageFileId || selectedImage.canvasFileId || selectedImage.fileId,
      userPrompt: userPrompt.trim(),
      finalPrompt: trimmedFinalPrompt,
      shotCount: Number(shotCount),
      aspectRatio,
      imageModel,
    })

    setOpen(false)
    setStep('form')
    setFinalPrompt('')
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        生成分镜
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {step === 'form' ? '生成分镜' : '确认分镜提示词'}
            </DialogTitle>
            <DialogDescription>
              {step === 'form'
                ? '先补充你的创作要求，再生成一份可直接执行的分镜提示词。'
                : '确认无误后再开始生成。右侧对话区只会记录这份最终提示词。'}
            </DialogDescription>
          </DialogHeader>

          {step === 'form' ? (
            <div className="grid gap-4 md:grid-cols-[220px_1fr]">
              <div className="rounded-xl border bg-muted/20 p-3">
                <div className="mb-3 text-sm font-medium text-foreground">
                  当前参考图
                </div>
                <div className="overflow-hidden rounded-lg border bg-background">
                  {previewUrl ? (
                    <img
                      src={previewUrl}
                      alt="Selected reference"
                      className="aspect-square h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex aspect-square items-center justify-center text-sm text-muted-foreground">
                      暂无预览
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium">补充要求</div>
                  <Textarea
                    value={userPrompt}
                    onChange={(event) => setUserPrompt(event.target.value)}
                    placeholder="例如：第一张更像广告开场，第二张推进动作，最后一张做收束定格。"
                    className="min-h-32"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <div className="text-sm font-medium">分镜张数</div>
                    <Input
                      type="number"
                      min={2}
                      max={8}
                      value={shotCount}
                      onChange={(event) => setShotCount(event.target.value)}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">画面比例</div>
                    <Select value={aspectRatio} onValueChange={setAspectRatio}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="16:9">16:9</SelectItem>
                        <SelectItem value="9:16">9:16</SelectItem>
                        <SelectItem value="1:1">1:1</SelectItem>
                        <SelectItem value="4:5">4:5</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">图片模型</div>
                    <Select
                      value={imageModel}
                      onValueChange={(value) =>
                        setImageModel(value as ImageModelOption)
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {IMAGE_MODEL_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border bg-muted/20 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                  <Sparkles className="h-4 w-4" />
                  最终提示词
                </div>
                <Textarea
                  value={finalPrompt}
                  onChange={(event) => setFinalPrompt(event.target.value)}
                  className="min-h-72"
                />
              </div>
              <div className="rounded-xl border border-dashed bg-background p-3 text-sm text-muted-foreground">
                你可以继续手动修改这份提示词。确认后才会进入右侧对话区并开始生成。
              </div>
            </div>
          )}

          <DialogFooter>
            {step === 'form' ? (
              <>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleBuildPrompt}>生成提示词</Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={() => setStep('form')}>
                  返回修改
                </Button>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleGenerateStoryboard}>
                  <Check className="mr-2 h-4 w-4" />
                  生成分镜图
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(CanvasStoryboardGenerator)
