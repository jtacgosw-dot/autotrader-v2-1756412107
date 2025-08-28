import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { TrendingUp, Download, RefreshCw } from 'lucide-react'

interface Position {
  pair: string
  side: 'BUY' | 'SELL'
  size: number
  avgPrice: number
  currentPrice: number
  pnl: number
  pnlPercent: number
}

interface Order {
  id: string
  timestamp: string
  venue: string
  pair: string
  side: 'BUY' | 'SELL'
  size: number
  price: number
  fees: number
  slippageBps: number
  latencyMs: number
  mode: 'paper' | 'live'
}

export function Orders() {
  const [positions, setPositions] = useState<Position[]>([
    {
      pair: 'BTC/USDT',
      side: 'BUY',
      size: 0.05,
      avgPrice: 29855.0,
      currentPrice: 30120.5,
      pnl: 13.28,
      pnlPercent: 0.89
    }
  ])

  const [recentOrders, setRecentOrders] = useState<Order[]>([
    {
      id: 'ord_001',
      timestamp: '2025-08-28T01:05:23Z',
      venue: 'binance',
      pair: 'BTC/USDT',
      side: 'BUY',
      size: 0.05,
      price: 29855.0,
      fees: 1.49,
      slippageBps: 1.8,
      latencyMs: 198,
      mode: 'paper'
    }
  ])

  const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [ordersResponse, positionsResponse] = await Promise.all([
          fetch(`${apiBase}/api/orders`, { credentials: 'include' }),
          fetch(`${apiBase}/api/positions`, { credentials: 'include' })
        ])
        
        if (ordersResponse.ok) {
          const ordersData = await ordersResponse.json()
          setRecentOrders(ordersData)
        }
        
        if (positionsResponse.ok) {
          const positionsData = await positionsResponse.json()
          setPositions(positionsData)
        }
      } catch (error) {
        console.error('Failed to fetch orders/positions:', error)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [apiBase])

  const exportData = (format: 'csv' | 'jsonl') => {
    const data = recentOrders.map(order => ({
      timestamp: order.timestamp,
      venue: order.venue,
      pair: order.pair,
      side: order.side,
      size: order.size,
      price: order.price,
      fees: order.fees,
      slippage_bps: order.slippageBps,
      latency_ms: order.latencyMs,
      mode: order.mode
    }))

    let content: string
    let filename: string

    if (format === 'csv') {
      const headers = Object.keys(data[0]).join(',')
      const rows = data.map(row => Object.values(row).join(','))
      content = [headers, ...rows].join('\n')
      filename = 'orders.csv'
    } else {
      content = data.map(row => JSON.stringify(row)).join('\n')
      filename = 'orders.jsonl'
    }

    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Orders & Positions</h1>
        <p className="text-muted-foreground">Current positions and recent trading activity</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <TrendingUp className="w-5 h-5 mr-2" />
              Open Positions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">No open positions</p>
            ) : (
              <div className="space-y-4">
                {positions.map((position, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-medium">{position.pair}</h4>
                        <Badge variant={position.side === 'BUY' ? 'default' : 'destructive'}>
                          {position.side}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <div className={`font-medium ${position.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ${position.pnl.toFixed(2)}
                        </div>
                        <div className={`text-sm ${position.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {position.pnlPercent >= 0 ? '+' : ''}{position.pnlPercent.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-sm text-muted-foreground">
                      <div>
                        <div>Size: {position.size}</div>
                        <div>Avg: ${position.avgPrice.toLocaleString()}</div>
                      </div>
                      <div>
                        <div>Current: ${position.currentPrice.toLocaleString()}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center">
                <RefreshCw className="w-5 h-5 mr-2" />
                Export Data
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <button
                onClick={() => exportData('csv')}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
              >
                <Download className="w-4 h-4 mr-2" />
                Export CSV
              </button>
              <button
                onClick={() => exportData('jsonl')}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
              >
                <Download className="w-4 h-4 mr-2" />
                Export JSONL
              </button>
              <button
                onClick={() => window.open(`${apiBase}/api/export/orders?format=csv`, '_blank')}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
              >
                <Download className="w-4 h-4 mr-2" />
                API Export CSV
              </button>
              <button
                onClick={() => window.open(`${apiBase}/api/export/positions?format=jsonl`, '_blank')}
                className="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
              >
                <Download className="w-4 h-4 mr-2" />
                API Export JSONL
              </button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Orders (Last 20)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Time</th>
                  <th className="text-left py-2">Venue</th>
                  <th className="text-left py-2">Pair</th>
                  <th className="text-left py-2">Side</th>
                  <th className="text-right py-2">Size</th>
                  <th className="text-right py-2">Price</th>
                  <th className="text-right py-2">Fees</th>
                  <th className="text-right py-2">Slippage</th>
                  <th className="text-right py-2">Latency</th>
                  <th className="text-center py-2">Mode</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((order) => (
                  <tr key={order.id} className="border-b">
                    <td className="py-2">{new Date(order.timestamp).toLocaleTimeString()}</td>
                    <td className="py-2 capitalize">{order.venue}</td>
                    <td className="py-2">{order.pair}</td>
                    <td className="py-2">
                      <Badge variant={order.side === 'BUY' ? 'default' : 'destructive'} className="text-xs">
                        {order.side}
                      </Badge>
                    </td>
                    <td className="py-2 text-right">{order.size}</td>
                    <td className="py-2 text-right">${order.price.toLocaleString()}</td>
                    <td className="py-2 text-right">${order.fees.toFixed(2)}</td>
                    <td className="py-2 text-right">{order.slippageBps} bps</td>
                    <td className="py-2 text-right">{order.latencyMs}ms</td>
                    <td className="py-2 text-center">
                      <Badge variant="secondary" className="text-xs">
                        {order.mode}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
