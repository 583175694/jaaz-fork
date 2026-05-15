import { previewDirectStoryboardPrompt } from '@/api/storyboard'
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
import { useConfigs } from '@/contexts/configs'
import { eventBus, TCanvasAddImagesToChatEvent } from '@/lib/event'
import { DEFAULT_IMAGE_MODEL, IMAGE_MODEL_OPTIONS, ImageModelOption } from '@/lib/imageModels'
import { Check, Sparkles } from 'lucide-react'
import { memo, useMemo, useState } from 'react'
import { toast } from 'sonner'

type CanvasStoryboardGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const CanvasStoryboardGenerator = ({
  selectedImages,
}: CanvasStoryboardGeneratorProps) => {
  const { mainImageFileId } = useCanvas()
  const { textModel } = useConfigs()
  const [open, setOpen] = useState(false)
  const [promptDraft, setPromptDraft] = useState('')
  const [isBuildingPrompt, setIsBuildingPrompt] = useState(false)
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
      setPromptDraft('')
      setShotCount('4')
      setAspectRatio('16:9')
      setImageModel(DEFAULT_IMAGE_MODEL)
    }
  }

  const handleBuildPrompt = async () => {
    if (!selectedImage) {
      toast.warning('请先选中一张图片')
      return
    }

    const trimmedPromptDraft = promptDraft.trim()
    if (!trimmedPromptDraft) {
      toast.warning('请先输入分镜需求')
      return
    }

    setIsBuildingPrompt(true)
    try {
      const result = await previewDirectStoryboardPrompt({
        textModel,
        prompt: trimmedPromptDraft,
        shotCount: Number(shotCount),
        aspectRatio,
      })
      const nextPrompt = String(result?.prompt || '').trim()
      if (!nextPrompt) {
        throw new Error('模型没有返回可用的分镜提示词')
      }
      setPromptDraft(nextPrompt)
    } catch (error) {
      console.error('Failed to build storyboard prompt:', error)
      toast.error('生成提示词失败', {
        description: String(error),
      })
    } finally {
      setIsBuildingPrompt(false)
    }
  }

  const handleGenerateStoryboard = () => {
    if (!selectedImage) {
      toast.warning('请先选中一张图片')
      return
    }

    const trimmedPromptDraft = promptDraft.trim()
    if (!trimmedPromptDraft) {
      toast.warning('请先输入分镜需求')
      return
    }

    eventBus.emit('Canvas::GenerateStoryboard', {
      selectedImage,
      mainImageFileId:
        mainImageFileId || selectedImage.canvasFileId || selectedImage.fileId,
      prompt: trimmedPromptDraft,
      shotCount: Number(shotCount),
      aspectRatio,
      imageModel,
    })

    setOpen(false)
    setPromptDraft('')
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        生成分镜
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-4xl overflow-hidden p-0">
          <div className="flex max-h-[calc(100vh-2rem)] flex-col">
            <DialogHeader className="shrink-0 border-b px-6 py-5">
              <DialogTitle>生成分镜</DialogTitle>
              <DialogDescription>
                先输入分镜需求。优化提示词是可选的；点击“生成分镜图”时，会直接使用当前输入框里的内容生成。
              </DialogDescription>
            </DialogHeader>

            <div className="flex-1 overflow-y-auto px-6 py-5">
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
                  <div className="rounded-xl border bg-muted/20 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                      <Sparkles className="h-4 w-4" />
                      分镜需求 / 提示词
                    </div>
                    <Textarea
                      value={promptDraft}
                      onChange={(event) => setPromptDraft(event.target.value)}
                      placeholder={
                        isBuildingPrompt
                          ? '正在优化提示词...'
                          : '先描述你想要的分镜结构、镜头推进、重点信息和收束方式。优化后会直接覆盖在这里，你也可以继续手动修改。'
                      }
                      className="min-h-72"
                    />
                  </div>

                  <div className="grid gap-4 md:grid-cols-3">
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
            </div>

            <DialogFooter className="shrink-0 border-t px-6 py-4">
              <Button variant="outline" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button
                onClick={handleBuildPrompt}
                disabled={isBuildingPrompt || !promptDraft.trim()}
              >
                {isBuildingPrompt ? '正在优化提示词...' : '优化提示词'}
              </Button>
              <Button
                onClick={handleGenerateStoryboard}
                disabled={isBuildingPrompt || !promptDraft.trim()}
              >
                <Check className="mr-2 h-4 w-4" />
                生成分镜图
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(CanvasStoryboardGenerator)
