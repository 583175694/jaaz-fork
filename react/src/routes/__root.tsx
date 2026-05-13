import ErrorBoundary from '@/components/common/ErrorBoundary'
import { createRootRoute, Outlet } from '@tanstack/react-router'

export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
    </>
  ),
  errorComponent: ErrorBoundary,
})
