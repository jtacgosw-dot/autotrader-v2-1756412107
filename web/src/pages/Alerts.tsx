import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { AlertTriangle, Bell, Clock, CheckCircle } from 'lucide-react'

interface Alert {
  id: string
  timestamp: string
  type: 'kill_switch' | 'venue_down' | 'high_latency' | 'error' | 'info'
  title: string
  message: string
  acknowledged: boolean
  severity: 'critical' | 'warning' | 'info'
}

export function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([
    {
      id: 'alert_001',
      timestamp: '2025-08-28T01:05:23Z',
      type: 'venue_down',
      title: 'Venue Connection Lost',
      message: 'Lost connection to Kraken exchange. Attempting reconnection.',
      acknowledged: false,
      severity: 'warning'
    },
    {
      id: 'alert_002',
      timestamp: '2025-08-28T00:45:12Z',
      type: 'high_latency',
      title: 'High Latency Detected',
      message: 'Binance latency exceeded 500ms threshold (p99: 650ms)',
      acknowledged: true,
      severity: 'warning'
    },
    {
      id: 'alert_003',
      timestamp: '2025-08-28T00:30:45Z',
      type: 'info',
      title: 'Trading Session Started',
      message: 'Arbitrage sleeve activated. Paper trading mode enabled.',
      acknowledged: true,
      severity: 'info'
    }
  ])

  const apiBase = import.meta.env.VITE_API_BASE || 'https://api.lunaraxolotl.com'

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const response = await fetch(`${apiBase}/api/alerts`, {
          credentials: 'include'
        })
        if (response.ok) {
          const data = await response.json()
          setAlerts(data)
        }
      } catch (error) {
        console.error('Failed to fetch alerts:', error)
      }
    }

    fetchAlerts()
    const interval = setInterval(fetchAlerts, 30000)
    return () => clearInterval(interval)
  }, [apiBase])

  const acknowledgeAlert = async (alertId: string) => {
    try {
      const response = await fetch(`${apiBase}/api/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        credentials: 'include'
      })
      if (response.ok) {
        setAlerts(prev => prev.map(alert => 
          alert.id === alertId ? { ...alert, acknowledged: true } : alert
        ))
      }
    } catch (error) {
      console.error('Failed to acknowledge alert:', error)
    }
  }

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'kill_switch': return <AlertTriangle className="w-5 h-5 text-red-600" />
      case 'venue_down': return <AlertTriangle className="w-5 h-5 text-yellow-600" />
      case 'high_latency': return <Clock className="w-5 h-5 text-yellow-600" />
      case 'error': return <AlertTriangle className="w-5 h-5 text-red-600" />
      case 'info': return <Bell className="w-5 h-5 text-blue-600" />
      default: return <Bell className="w-5 h-5 text-gray-600" />
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'critical': return 'destructive'
      case 'warning': return 'secondary'
      case 'info': return 'default'
      default: return 'secondary'
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'border-red-800 bg-red-950/20'
      case 'warning': return 'border-yellow-800 bg-yellow-950/20'
      case 'info': return 'border-blue-800 bg-blue-950/20'
      default: return 'border-border bg-muted/20'
    }
  }

  const unacknowledgedCount = alerts.filter(alert => !alert.acknowledged).length
  const criticalCount = alerts.filter(alert => alert.severity === 'critical' && !alert.acknowledged).length

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
        <p className="text-muted-foreground">System alerts and notifications</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Alerts</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{alerts.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Unacknowledged</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{unacknowledgedCount}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Critical</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{criticalCount}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {alerts.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">No alerts to display</p>
            ) : (
              alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`border rounded-lg p-4 ${getSeverityColor(alert.severity)} ${
                    alert.acknowledged ? 'opacity-60' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      {getAlertIcon(alert.type)}
                      <div className="flex-1">
                        <div className="flex items-center space-x-2 mb-1">
                          <h4 className="font-medium text-foreground">{alert.title}</h4>
                          <Badge variant={getSeverityVariant(alert.severity)}>
                            {alert.severity}
                          </Badge>
                          {alert.acknowledged && (
                            <CheckCircle className="w-4 h-4 text-green-600" />
                          )}
                        </div>
                        <p className="text-muted-foreground text-sm mb-2">{alert.message}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(alert.timestamp).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    {!alert.acknowledged && (
                      <button
                        onClick={() => acknowledgeAlert(alert.id)}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium py-1 px-3 rounded-md transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
