import { Input } from '@/components/ui/input'
import CanvasExport from './CanvasExport'
import TopMenu from '../TopMenu'

type CanvasHeaderProps = {
  canvasName: string
  canvasId: string
  onNameChange: (name: string) => void
  onNameSave: () => void
}

const CanvasHeader: React.FC<CanvasHeaderProps> = ({
  canvasName,
  onNameChange,
  onNameSave,
}) => {
  return (
    <TopMenu
      middle={
        <Input
          className="h-10 min-w-[12rem] w-full max-w-md rounded-xl border border-transparent bg-foreground/[0.03] px-4 text-center text-sm font-medium text-foreground shadow-none transition-all hover:border-border/70 hover:bg-background focus-visible:border-ring"
          value={canvasName}
          onChange={(e) => onNameChange(e.target.value)}
          onBlur={onNameSave}
        />
      }
      right={<CanvasExport />}
    />
  )
}

export default CanvasHeader
