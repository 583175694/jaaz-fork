import { createFileRoute, Navigate } from '@tanstack/react-router'

export const Route = createFileRoute('/knowledge')({
  component: RouteComponent,
})

function RouteComponent() {
  return <Navigate to='/' />
}
