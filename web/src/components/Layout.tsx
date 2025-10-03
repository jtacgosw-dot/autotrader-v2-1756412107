import { ReactNode, useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Activity, BarChart3, Shield, AlertTriangle, TrendingUp, LogOut, User } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { Badge } from './ui/badge'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { user, logout } = useAuth()
  const [maintenanceMode, setMaintenanceMode] = useState(false)
  const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'
  
  useKeyboardShortcuts()

  useEffect(() => {
    fetch(`${apiBase}/api/maintenance`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => setMaintenanceMode(data.maintenance_mode))
      .catch(() => {})
  }, [apiBase])

  const navigation = [
    { name: 'Overview', href: '/overview', icon: Activity, roles: ['viewer', 'controller'] },
    { name: 'Live Feed', href: '/live', icon: Activity, roles: ['viewer', 'controller'] },
    { name: 'Venues & Latency', href: '/venues', icon: BarChart3, roles: ['viewer', 'controller'] },
    { name: 'Orders & Positions', href: '/orders', icon: TrendingUp, roles: ['viewer', 'controller'] },
    { name: 'Risk & Controls', href: '/risk', icon: Shield, roles: ['controller'] },
    { name: 'Alerts', href: '/alerts', icon: AlertTriangle, roles: ['viewer', 'controller'] },
  ]

  const visibleNavigation = navigation.filter(item => 
    user && item.roles.includes(user.role)
  )

  const handleLogout = async () => {
    await logout()
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="bg-card shadow-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-bold text-foreground">Lunar Axolotl Trading</h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                {visibleNavigation.map((item) => {
                  const Icon = item.icon
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`${
                        isActive
                          ? 'border-primary text-foreground'
                          : 'border-transparent text-muted-foreground hover:border-muted hover:text-foreground'
                      } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium`}
                    >
                      <Icon className="w-4 h-4 mr-2" />
                      {item.name}
                    </Link>
                  )
                })}
              </div>
            </div>
            <div className="flex items-center space-x-2 sm:space-x-4">
              <div className="hidden sm:block text-sm text-muted-foreground">Paper Trading Mode</div>
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              {user && (
                <div className="flex items-center space-x-2 sm:space-x-3">
                  <div className="hidden sm:flex items-center space-x-2 text-sm">
                    <User className="w-4 h-4" />
                    <span className="hidden md:inline">{user.username}</span>
                    <Badge variant={user.role === 'controller' ? 'default' : 'secondary'}>
                      {user.role}
                    </Badge>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="text-muted-foreground hover:text-foreground"
                    title="Logout"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
      {import.meta.env.VITE_ENV === 'prod' && (
        <div className="bg-blue-600 text-white text-center py-1 text-sm">
          🔵 Production Environment
        </div>
      )}
      {maintenanceMode && (
        <div className="bg-yellow-600 text-white text-center py-1 text-sm">
          ⚠️ Maintenance Mode Active - Trading Disabled
        </div>
      )}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {children}
      </main>
      <footer className="border-t border-border mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center text-sm text-muted-foreground">
            <div>
              AutoTrader v2 | Build: {import.meta.env.VITE_BUILD_SHA?.substring(0, 7) || 'dev'} | 
              {' '}{import.meta.env.VITE_BUILD_TIME || 'local'}
            </div>
            <div>
              API: {import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'} | 
              Env: {import.meta.env.VITE_ENV || 'dev'}
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
