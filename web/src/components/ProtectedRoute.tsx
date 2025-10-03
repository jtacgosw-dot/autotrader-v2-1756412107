import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  requireRole?: 'viewer' | 'controller'
}

export function ProtectedRoute({ children, requireRole }: ProtectedRouteProps) {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">
      <div className="text-lg">Loading...</div>
    </div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (requireRole === 'controller' && user.role !== 'controller') {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
