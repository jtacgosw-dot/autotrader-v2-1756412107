import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Activity } from 'lucide-react'

interface TradeEvent {
  ts: string
  venue: string
  symbol: string
  side: string
  qty: number
  notional: number
  lat_ms: number
  status: string
  pnl_usd: number
  equity_usd: number
  order_id: string
}

interface HealthEvent {
  discord_webhook_ok: boolean
  ssm_ok: boolean
  api_ok: boolean
  overall_status: string
  timestamp: string
}

export function LiveFeed() {
  const [trades, setTrades] = useState<TradeEvent[]>([])
  const [health, setHealth] = useState<HealthEvent | null>(null)
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [reconnectCountdown, setReconnectCountdown] = useState(0)
  const [filter, setFilter] = useState({ venue: 'all', symbol: 'all' })
  const tradesEventSource = useRef<EventSource | null>(null)
  const healthEventSource = useRef<EventSource | null>(null)

  useEffect(() => {
    let reconnectAttempts = 0
    let healthReconnectAttempts = 0
    const maxReconnectAttempts = 10
    let lastTradeTimestamp = ''
    let reconnectTimer: NodeJS.Timeout | null = null

    const connectSSE = () => {
      const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'
      
      tradesEventSource.current = new EventSource(`${apiBase}/api/stream/trades`, {
        withCredentials: true
      })

      tradesEventSource.current.onopen = () => {
        setConnected(true)
        setReconnecting(false)
        reconnectAttempts = 0
      }

      tradesEventSource.current.onmessage = (event) => {
        try {
          const tradeEvent: TradeEvent = JSON.parse(event.data)
          if (tradeEvent.ts) {
            lastTradeTimestamp = tradeEvent.ts
          }
          setTrades(prev => [tradeEvent, ...prev.slice(0, 999)])
        } catch (e) {
          console.error('Failed to parse trade event:', e)
        }
      }

      tradesEventSource.current.onerror = () => {
        setConnected(false)
        tradesEventSource.current?.close()
        
        if (reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++
          setReconnecting(true)
          const backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000) + Math.random() * 1000
          
          setReconnectCountdown(Math.floor(backoffDelay / 1000))
          if (reconnectTimer) clearInterval(reconnectTimer)
          reconnectTimer = setInterval(() => {
            setReconnectCountdown(prev => Math.max(0, prev - 1))
          }, 1000)
          
          setTimeout(() => {
            if (reconnectTimer) clearInterval(reconnectTimer)
            if (lastTradeTimestamp) {
              const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'
              fetch(`${apiBase}/api/trades?since=${lastTradeTimestamp}&limit=50`, { credentials: 'include' })
                .then(res => res.json())
                .then(data => {
                  if (data.trades && data.trades.length > 0) {
                    setTrades(prev => [...data.trades.reverse(), ...prev.slice(0, 999)])
                  }
                })
                .catch(console.error)
            }
            connectSSE()
          }, backoffDelay)
        } else {
          setReconnecting(false)
        }
      }
    }

    const connectHealthSSE = () => {
      const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'
      
      healthEventSource.current = new EventSource(`${apiBase}/api/stream/health`, {
        withCredentials: true
      })

      healthEventSource.current.onmessage = (event) => {
        try {
          const healthEvent: HealthEvent = JSON.parse(event.data)
          setHealth(healthEvent)
          healthReconnectAttempts = 0
        } catch (e) {
          console.error('Failed to parse health event:', e)
        }
      }

      healthEventSource.current.onerror = () => {
        healthEventSource.current?.close()
        
        if (healthReconnectAttempts < maxReconnectAttempts) {
          healthReconnectAttempts++
          const backoffDelay = Math.min(1000 * Math.pow(2, healthReconnectAttempts), 30000) + Math.random() * 1000
          setTimeout(connectHealthSSE, backoffDelay)
        }
      }
    }

    connectSSE()
    connectHealthSSE()

    const apiBase = import.meta.env.VITE_API_BASE || 'https://lunaraxolotl.com'
    fetch(`${apiBase}/api/trades?limit=50`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => setTrades(data.trades || []))
      .catch(console.error)

    return () => {
      if (reconnectTimer) clearInterval(reconnectTimer)
      tradesEventSource.current?.close()
      healthEventSource.current?.close()
    }
  }, [])

  const filteredTrades = trades.filter(trade => {
    if (filter.venue !== 'all' && trade.venue !== filter.venue) return false
    if (filter.symbol !== 'all' && trade.symbol !== filter.symbol) return false
    return true
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Live Feed</h1>
        <div className="flex items-center space-x-4">
          <Badge variant={connected ? "default" : reconnecting ? "secondary" : "destructive"}>
            {connected ? "Connected" : reconnecting ? `Reconnecting in ${reconnectCountdown}s` : "Disconnected"}
          </Badge>
          <div className="flex space-x-2">
            <select 
              value={filter.venue} 
              onChange={(e) => setFilter(prev => ({...prev, venue: e.target.value}))}
              className="px-3 py-1 border rounded"
            >
              <option value="all">All Venues</option>
              <option value="binance">Binance</option>
              <option value="paper">Paper</option>
            </select>
            <select 
              value={filter.symbol} 
              onChange={(e) => setFilter(prev => ({...prev, symbol: e.target.value}))}
              className="px-3 py-1 border rounded"
            >
              <option value="all">All Symbols</option>
              <option value="BTC/USDT">BTC/USDT</option>
              <option value="ETH/USDT">ETH/USDT</option>
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Activity className="w-5 h-5 mr-2" />
                Live Trades
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {filteredTrades.map((trade, index) => (
                  <div key={`${trade.order_id}-${index}`} className="flex justify-between items-center p-3 bg-muted rounded">
                    <div className="flex items-center space-x-3">
                      <Badge variant={trade.side === 'BUY' ? 'default' : 'destructive'}>
                        {trade.side}
                      </Badge>
                      <span className="font-mono">{trade.symbol}</span>
                      <span className="text-sm text-muted-foreground">{trade.venue}</span>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">${trade.notional?.toFixed(2) ?? 'N/A'}</div>
                      <div className="text-sm text-muted-foreground">{trade.lat_ms ?? 0}ms</div>
                    </div>
                  </div>
                ))}
                {filteredTrades.length === 0 && (
                  <div className="text-center text-muted-foreground py-8">
                    No trades yet. Try the smoke trade button!
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent>
              {health && (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span>API</span>
                    <Badge variant={health.api_ok ? "default" : "destructive"}>
                      {health.api_ok ? "OK" : "Error"}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Discord</span>
                    <Badge variant={health.discord_webhook_ok ? "default" : "destructive"}>
                      {health.discord_webhook_ok ? "OK" : "Error"}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>SSM</span>
                    <Badge variant={health.ssm_ok ? "default" : "destructive"}>
                      {health.ssm_ok ? "OK" : "Error"}
                    </Badge>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
