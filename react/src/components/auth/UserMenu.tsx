import React from 'react'
import { APP_NAME } from '@/constants'
import { Button } from '@/components/ui/button'

export function UserMenu() {
  return (
    <Button variant="outline" disabled>
      {APP_NAME}
    </Button>
  )
}
