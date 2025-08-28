import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { BarChart3, Wifi, WifiOff, Clock } from 'lucide-react'

interface VenueStatus {
  name: string
  status: 'connected' | 'disconnected' | 'degraded'
  latency: {
    p50: number
    p95: number
    p99: number
  }
  rejectRate: number
  reconnects: number
  circuitBreaker: boolean
}

export function Venues() {
  const [venues, setVenues] = useState<VenueStatus[]>([
    {
      name: 'Binance',
      status: 'connected',
      latency: { p50: 45, p95: 120, p99: 250 },
      rejectRate: 0.2,
      reconnects: 0,
      circuitBreaker: false
    },
    {
      name: 'Coinbase',
      status: 'connected',
      latency: { p50: 65, p95: 180, p99: 320 },
      rejectRate: 0.1,
      reconnects: 1,
      circuitBreaker: false
    },
    {
      name: 'Kraken',
      status: 'degraded',
      latency: { p50: 120, p95: 450, p99: 800 },
      rejectRate: 2.1,
      reconnects: 3,
      circuitBreaker: true
    }
  ])

  const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'

  useEffect(() => {
    const fetchVenues = async () => {
      try {
        const response = await fetch(`${apiBase}/api/venues`, {
          credentials: 'include'
        })
        if (response.ok) {
          const data = await response.json()
          setVenues(data)
        }
      } catch (error) {
        console.error('Failed to fetch venue status:', error)
      }
    }

    fetchVenues()
    const interval = setInterval(fetchVenues, 10000)
    return () => clearInterval(interval)
  }, [apiBase])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected': return <Wifi className="w-4 h-4 text-green-400" />
      case 'disconnected': return <WifiOff className="w-4 h-4 text-red-400" />
      case 'degraded': return <Wifi className="w-4 h-4 text-yellow-400" />
      default: return <WifiOff className="w-4 h-4 text-muted-foreground" />
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'connected': return 'default'
      case 'disconnected': return 'destructive'
      case 'degraded': return 'secondary'
      default: return 'secondary'
    }
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Venues & Latency</h1>
        <p className="text-muted-foreground">Real-time venue connectivity and performance metrics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {venues.map((venue) => (
          <Card key={venue.name}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{venue.name}</span>
                <div className="flex items-center space-x-2">
                  {getStatusIcon(venue.status)}
                  <Badge variant={getStatusVariant(venue.status)}>
                    {venue.status}
                  </Badge>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-foreground mb-2 flex items-center">
                    <Clock className="w-4 h-4 mr-1" />
                    Latency (ms)
                  </h4>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="text-center">
                      <div className="font-medium">{venue.latency.p50}</div>
                      <div className="text-muted-foreground">p50</div>
                    </div>
                    <div className="text-center">
                      <div className="font-medium">{venue.latency.p95}</div>
                      <div className="text-muted-foreground">p95</div>
                    </div>
                    <div className="text-center">
                      <div className="font-medium">{venue.latency.p99}</div>
                      <div className="text-muted-foreground">p99</div>
                    </div>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">Reject Rate</div>
                    <div className="font-medium">{venue.rejectRate}%</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Reconnects</div>
                    <div className="font-medium">{venue.reconnects}</div>
                  </div>
                </div>

                {venue.circuitBreaker && (
                  <div className="bg-yellow-900/20 border border-yellow-600 rounded-md p-3">
                    <div className="flex items-center">
                      <BarChart3 className="w-4 h-4 text-yellow-400 mr-2" />
                      <span className="text-sm text-yellow-300">Circuit Breaker Active</span>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
