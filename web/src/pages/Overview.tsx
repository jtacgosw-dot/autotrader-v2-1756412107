import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { TrendingUp, TrendingDown, DollarSign, Activity, CheckCircle, XCircle } from 'lucide-react'

interface HealthStatus {
  api_ok: boolean
  nginx_ok: boolean
  tg_healthy: boolean
  ssm_ok: boolean
  discord_webhook_ok: boolean
  overall_status: string
  timestamp: string
}

interface BotStatus {
  status: string
  totalEquity: number
  pnlToday: number
  drawdown: number
  sleeves: {
    arbitrage: string
    swing: string
    event: string
  }
}

export function Overview() {
  const [botStatus, setBotStatus] = useState<BotStatus>({
    status: 'running',
    totalEquity: 100000,
    pnlToday: 1250.75,
    drawdown: 0.35,
    sleeves: {
      arbitrage: 'active',
      swing: 'inactive',
      event: 'inactive'
    }
  })

  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)

  const apiBase = import.meta.env.VITE_API_BASE || 'https://api.lunaraxolotl.com'

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${apiBase}/api/status`, {
          credentials: 'include'
        })
        if (response.ok) {
          const data = await response.json()
          setBotStatus(data)
        }
      } catch (error) {
        console.error('Failed to fetch bot status:', error)
      }
    }

    const fetchHealthStatus = async () => {
      try {
        const response = await fetch(`${apiBase}/api/healthz`, {
          credentials: 'include'
        })
        if (response.ok) {
          const data = await response.json()
          setHealthStatus(data)
        }
      } catch (error) {
        console.error('Failed to fetch health status:', error)
      }
    }

    fetchStatus()
    fetchHealthStatus()
    const interval = setInterval(() => {
      fetchStatus()
      fetchHealthStatus()
    }, 5000)
    return () => clearInterval(interval)
  }, [apiBase])

  const getHealthBadge = (status: boolean, label: string) => (
    <div className="flex items-center space-x-2">
      {status ? (
        <CheckCircle className="w-4 h-4 text-green-600" />
      ) : (
        <XCircle className="w-4 h-4 text-red-600" />
      )}
      <span className="text-sm">{label}</span>
      <Badge variant={status ? "default" : "destructive"}>
        {status ? "OK" : "ERROR"}
      </Badge>
    </div>
  )

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-500'
      case 'paused': return 'bg-yellow-500'
      case 'stopped': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getSleeveStatus = (status: string) => {
    switch (status) {
      case 'active': return 'default'
      case 'inactive': return 'secondary'
      case 'error': return 'destructive'
      default: return 'secondary'
    }
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Trading Overview</h1>
        <p className="text-muted-foreground">Real-time status of your autonomous trading system</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Bot Status</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${getStatusColor(botStatus.status)}`}></div>
              <span className="text-2xl font-bold capitalize">{botStatus.status}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Equity</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${botStatus.totalEquity.toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">P&amp;L Today</CardTitle>
            {botStatus.pnlToday >= 0 ? (
              <TrendingUp className="h-4 w-4 text-green-400" />
            ) : (
              <TrendingDown className="h-4 w-4 text-red-400" />
            )}
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${botStatus.pnlToday >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${botStatus.pnlToday.toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Drawdown</CardTitle>
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{botStatus.drawdown.toFixed(2)}%</div>
            <p className="text-xs text-muted-foreground">Kill switch at 1.0%</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Trading Sleeves</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">Arbitrage</span>
                <Badge variant={getSleeveStatus(botStatus.sleeves.arbitrage)}>
                  {botStatus.sleeves.arbitrage}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium">Swing</span>
                <Badge variant={getSleeveStatus(botStatus.sleeves.swing)}>
                  {botStatus.sleeves.swing}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium">Event</span>
                <Badge variant={getSleeveStatus(botStatus.sleeves.event)}>
                  {botStatus.sleeves.event}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <button 
                onClick={() => window.open(import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3000', '_blank')}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
              >
                View Grafana Dashboard
              </button>
              <button 
                onClick={() => window.open(`${import.meta.env.VITE_API_BASE || 'https://api.lunaraxolotl.com'}/api/healthz`, '_blank')}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
              >
                Check API Health
              </button>
            </div>
          </CardContent>
        </Card>
      </div>

      {healthStatus && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>System Health Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              {getHealthBadge(healthStatus.api_ok, "API")}
              {getHealthBadge(healthStatus.nginx_ok, "Nginx")}
              {getHealthBadge(healthStatus.tg_healthy, "Target Group")}
              {getHealthBadge(healthStatus.ssm_ok, "SSM")}
              {getHealthBadge(healthStatus.discord_webhook_ok, "Discord")}
            </div>
            <div className="mt-4 flex items-center space-x-2">
              <span className="text-sm font-medium">Overall Status:</span>
              <Badge variant={
                healthStatus.overall_status === "healthy" ? "default" :
                healthStatus.overall_status === "degraded" ? "secondary" : "destructive"
              }>
                {healthStatus.overall_status.toUpperCase()}
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
