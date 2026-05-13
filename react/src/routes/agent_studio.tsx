import { createFileRoute, Navigate } from '@tanstack/react-router'

export const Route = createFileRoute('/agent_studio')({
  component: RouteComponent,
})

function RouteComponent() {
  return <Navigate to='/' />
}
