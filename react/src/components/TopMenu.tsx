import { Button } from '@/components/ui/button'
import { ChevronLeft } from 'lucide-react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from '@tanstack/react-router'
import ThemeButton from '@/components/theme/ThemeButton'
import { APP_NAME, LOGO_URL } from '@/constants'
import LanguageSwitcher from './common/LanguageSwitcher'

export default function TopMenu({
  middle,
  right,
}: {
  middle?: React.ReactNode
  right?: React.ReactNode
}) {
  const { t } = useTranslation()
  const isHome = window.location.pathname === '/'

  const navigate = useNavigate()
  return (
    <motion.div
      className="sticky top-0 z-10 flex h-13 w-full items-center justify-between border-b border-border/80 bg-background/92 px-4 backdrop-blur-md select-none shadow-[0_1px_0_rgba(15,23,42,0.04)]"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex min-w-0 flex-1 items-center">
        <motion.div
          className="group flex h-10 max-w-[22rem] items-center gap-2 rounded-xl px-2.5 transition-colors duration-200 cursor-pointer hover:bg-accent/70"
          onClick={() => navigate({ to: '/' })}
        >
          {!isHome && (
            <div className="flex size-8 items-center justify-center rounded-lg bg-foreground/[0.045] text-foreground/80 transition-all duration-300 group-hover:-translate-x-0.5 group-hover:bg-foreground/[0.08] group-hover:text-foreground">
              <ChevronLeft className="size-4" />
            </div>
          )}
          <img
            src={LOGO_URL}
            alt="logo"
            className="size-6 rounded-md shadow-sm"
            draggable={false}
          />
          <motion.div className="relative flex h-8 min-w-0 items-center overflow-hidden">
            <motion.span className="flex items-center" layout>
              <span className="truncate text-[17px] font-semibold tracking-[0.01em] text-foreground">
                {isHome ? APP_NAME : t('canvas:back')}
              </span>
            </motion.span>
          </motion.div>
        </motion.div>
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-center px-4">
        {middle}
      </div>

      <div className="flex flex-1 items-center justify-end gap-2">
        {right}
        <LanguageSwitcher />
        <ThemeButton />
      </div>
    </motion.div>
  )
}
