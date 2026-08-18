import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { LoadingState } from '../components/LoadingState'
import { useAuth } from './AuthContext'

export function ProtectedRoute() {
  const { isLoading, session } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingState label="Preparando tu espacio" fullScreen />
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
