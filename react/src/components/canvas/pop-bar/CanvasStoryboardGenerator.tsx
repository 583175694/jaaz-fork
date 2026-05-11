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
import { memo, useMemo, useState } from 'react'
import { toast } from 'sonner'

type CanvasStoryboardGeneratorProps = {
  selectedImages: TCanvasAddImagesToChatEvent
}

const CanvasStoryboardGenerator = ({
  selectedImages,
}: CanvasStoryboardGeneratorProps) => {
  const { mainImageFileId } = useCanvas()
  const [open, setOpen] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [shotCount, setShotCount] = useState('4')
  const [variantCount, setVariantCount] = useState('3')
  const [aspectRatio, setAspectRatio] = useState('16:9')

  const selectedImage = selectedImages[0]
  const previewUrl = useMemo(
    () => selectedImage?.base64 || '',
    [selectedImage?.base64]
  )

  const handleGenerateStoryboard = () => {
    if (!selectedImage) {
      toast.warning('请先选中一张主图')
      return
    }

    eventBus.emit('Canvas::GenerateStoryboard', {
      selectedImage,
      mainImageFileId: mainImageFileId || selectedImage.canvasFileId || selectedImage.fileId,
      prompt: prompt.trim(),
      shotCount: Number(shotCount),
      variantCountPerShot: Number(variantCount),
      aspectRatio,
    })

    setOpen(false)
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        主图分镜
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>主图 / 首帧生成分镜</DialogTitle>
            <DialogDescription>
              先定义镜头数和后续扩展预算，提交后会先进入中文 Prompt 确认。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-[220px_1fr]">
            <div className="rounded-xl border bg-muted/20 p-3">
              <div className="mb-3 text-sm font-medium text-foreground">
                当前主图
              </div>
              <div className="overflow-hidden rounded-lg border bg-background">
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Selected main image"
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
                <div className="text-sm font-medium">中文创意补充</div>
                <Textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="例如：强化广告开场、动作推进、反应特写和最终 hero 收束。"
                  className="min-h-28"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <div className="text-sm font-medium">镜头数</div>
                  <Input
                    type="number"
                    min={2}
                    max={8}
                    value={shotCount}
                    onChange={(event) => setShotCount(event.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">后续扩展预算</div>
                  <Input
                    type="number"
                    min={1}
                    max={4}
                    value={variantCount}
                    onChange={(event) => setVariantCount(event.target.value)}
                  />
                  <div className="text-xs text-muted-foreground">
                    首轮每镜只生成 1 个 primary 镜头，这里定义后续同镜扩展上限。
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">比例</div>
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
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={handleGenerateStoryboard}>进入确认</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default memo(CanvasStoryboardGenerator)
