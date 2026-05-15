import { createCanvas, listCanvases } from '@/api/canvas'
import CanvasCard from '@/components/home/CanvasCard'
import NewCanvasCard from '@/components/home/NewCanvasCard'
import { useConfigs } from '@/contexts/configs'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { AnimatePresence, motion } from 'motion/react'
import { nanoid } from 'nanoid'
import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

const CanvasList: React.FC = () => {
  const { t } = useTranslation()
  const location = useLocation()
  const isHomePage = location.pathname === '/'
  const navigate = useNavigate()
  const { setInitCanvas, textModel, selectedTools } = useConfigs()

  const { data: canvases, refetch } = useQuery({
    queryKey: ['canvases'],
    queryFn: listCanvases,
    enabled: isHomePage, // 每次进入首页时都重新查询
    refetchOnMount: 'always',
  })

  const handleCanvasClick = (id: string) => {
    navigate({ to: '/canvas/$id', params: { id } })
  }

  const handleCreateBlankCanvas = async () => {
    if (!textModel) {
      toast.error(t('chat:textarea.selectModel'))
      return
    }

    const sessionId = nanoid()

    try {
      const data = await createCanvas({
        name: t('home:newCanvas'),
        canvas_id: nanoid(),
        messages: [],
        session_id: sessionId,
        text_model: {
          provider: textModel.provider,
          model: textModel.model,
          url: textModel.url,
        },
        tool_list: selectedTools,
        system_prompt: localStorage.getItem('system_prompt') || '',
      })

      setInitCanvas(false)
      navigate({
        to: '/canvas/$id',
        params: { id: data.id },
        search: { sessionId },
      })
    } catch (error) {
      toast.error(t('common:messages.error'), {
        description: error instanceof Error ? error.message : String(error),
      })
    }
  }

  return (
    <div className="flex flex-col px-10 mt-10 gap-4 select-none max-w-[1200px] mx-auto">
      {isHomePage && (
        <motion.span
          className="text-2xl font-bold"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {t('home:allProjects')}
        </motion.span>
      )}

      <AnimatePresence>
        <div className="grid grid-cols-4 gap-4 w-full pb-10">
          {isHomePage && (
            <NewCanvasCard
              index={0}
              onClick={() => {
                void handleCreateBlankCanvas()
              }}
            />
          )}
          {canvases?.map((canvas, index) => (
            <CanvasCard
              key={canvas.id}
              index={index + (isHomePage ? 1 : 0)}
              canvas={canvas}
              handleCanvasClick={handleCanvasClick}
              handleDeleteCanvas={() => refetch()}
            />
          ))}
        </div>
      </AnimatePresence>
    </div>
  )
}

export default memo(CanvasList)
