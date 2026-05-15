import { Plus } from 'lucide-react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'

type NewCanvasCardProps = {
  index: number
  onClick: () => void
}

const NewCanvasCard: React.FC<NewCanvasCardProps> = ({ index, onClick }) => {
  const { t } = useTranslation()

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className="border border-dashed border-primary/35 rounded-xl cursor-pointer hover:border-primary/55 transition-all duration-300 hover:shadow-md hover:bg-primary/5 active:scale-99 text-left"
      onClick={onClick}
    >
      <div className="p-3 flex flex-col gap-2">
        <div className="w-full h-40 rounded-lg border border-dashed border-primary/25 bg-primary/5 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-primary">
            <div className="w-12 h-12 rounded-full bg-background/90 border border-primary/20 flex items-center justify-center">
              <Plus className="w-6 h-6" />
            </div>
            <span className="text-sm font-medium">{t('home:createBlankCanvasHint')}</span>
          </div>
        </div>
        <div className="flex flex-col">
          <h3 className="text-lg font-bold">{t('home:createBlankCanvas')}</h3>
          <p className="text-sm text-gray-500">{t('home:createBlankCanvasDescription')}</p>
        </div>
      </div>
    </motion.button>
  )
}

export default NewCanvasCard
