import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Badge } from '../components/ui/badge'
import { Shield, Play, Pause, AlertTriangle, DollarSign } from 'lucide-react'

interface RiskSettings {
  dailyKillPct: number
  maxPosPct: number
  maxSlippageBps: number
  currentDrawdown: number
  botStatus: 'running' | 'paused' | 'stopped'
  killSwitchActive: boolean
}

interface WalletBalance {
  currency: string
  balance: number
  usdValue: number
  available: number
  locked: number
}

interface PaperTradingConfig {
  initial_capital: number
  max_position_size: number
  mode: string
}

export function Risk() {
  const [riskSettings, setRiskSettings] = useState<RiskSettings>({
    dailyKillPct: 1.0,
    maxPosPct: 1.0,
    maxSlippageBps: 6,
    currentDrawdown: 0.35,
    botStatus: 'running',
    killSwitchActive: false
  })

  const [maintenanceMode, setMaintenanceMode] = useState(false)

  const [walletBalances, setWalletBalances] = useState<WalletBalance[]>([
    { currency: 'USDT', balance: 95000, usdValue: 95000, available: 95000, locked: 0 },
    { currency: 'BTC', balance: 0.05, usdValue: 1506, available: 0, locked: 0.05 },
    { currency: 'ETH', balance: 1.2, usdValue: 3494, available: 1.2, locked: 0 }
  ])

  const [paperTradingConfig, setPaperTradingConfig] = useState<PaperTradingConfig>({
    initial_capital: 100000,
    max_position_size: 0.5,
    mode: 'paper'
  })

  const [isUpdating, setIsUpdating] = useState(false)
  const apiBase = import.meta.env.VITE_API_BASE || 'https://api.lunaraxolotl.com'

  useEffect(() => {
    const fetchRiskData = async () => {
      try {
        const [riskResponse, balanceResponse, maintenanceResponse, configResponse] = await Promise.all([
          fetch(`${apiBase}/api/risk`, { credentials: 'include' }),
          fetch(`${apiBase}/api/balances`, { credentials: 'include' }),
          fetch(`${apiBase}/api/maintenance`, { credentials: 'include' }),
          fetch(`${apiBase}/api/config/paper-trading`, { credentials: 'include' })
        ])
        
        if (riskResponse.ok) {
          const riskData = await riskResponse.json()
          setRiskSettings(riskData)
        }
        
        if (balanceResponse.ok) {
          const balanceData = await balanceResponse.json()
          const balanceArray = Object.entries(balanceData).map(([currency, data]: [string, any]) => ({
            currency,
            balance: data.balance,
            usdValue: data.usd_value || 0,
            available: data.available || 0,
            locked: data.locked || 0
          }))
          setWalletBalances(balanceArray)
        }
        
        if (maintenanceResponse.ok) {
          const maintenanceData = await maintenanceResponse.json()
          setMaintenanceMode(maintenanceData.maintenance_mode || false)
        }
        
        if (configResponse.ok) {
          const configData = await configResponse.json()
          setPaperTradingConfig(configData)
        }
      } catch (error) {
        console.error('Failed to fetch risk data:', error)
      }
    }

    fetchRiskData()
    const interval = setInterval(fetchRiskData, 10000)
    return () => clearInterval(interval)
  }, [apiBase])

  const toggleMaintenanceMode = async () => {
    try {
      const response = await fetch(`${apiBase}/api/maintenance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ enabled: !maintenanceMode })
      })
      
      if (response.ok) {
        setMaintenanceMode(!maintenanceMode)
      }
    } catch (error) {
      console.error('Failed to toggle maintenance mode:', error)
    }
  }

  const handlePause = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/pause`, {
        method: 'POST',
        credentials: 'include'
      })
      if (response.ok) {
        setRiskSettings(prev => ({ ...prev, botStatus: 'paused' }))
      }
    } catch (error) {
      console.error('Failed to pause bot:', error)
    }
    setIsUpdating(false)
  }

  const handleResume = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/resume`, {
        method: 'POST',
        credentials: 'include'
      })
      if (response.ok) {
        setRiskSettings(prev => ({ ...prev, botStatus: 'running' }))
      }
    } catch (error) {
      console.error('Failed to resume bot:', error)
    }
    setIsUpdating(false)
  }

  const handleRiskUpdate = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/risk`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          daily_kill_pct: riskSettings.dailyKillPct,
          max_pos_pct: riskSettings.maxPosPct,
          max_slippage_bps: riskSettings.maxSlippageBps
        })
      })
      if (!response.ok) {
        throw new Error('Failed to update risk settings')
      }
    } catch (error) {
      console.error('Failed to update risk settings:', error)
    }
    setIsUpdating(false)
  }

  const resetKillSwitch = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/reset-kill-switch`, {
        method: 'POST',
        credentials: 'include'
      })
      if (response.ok) {
        setRiskSettings(prev => ({ ...prev, killSwitchActive: false, currentDrawdown: 0 }))
      }
    } catch (error) {
      console.error('Failed to reset kill switch:', error)
    }
    setIsUpdating(false)
  }

  const handleSmokeTradeTest = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/test/smoke_trade`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          symbol: 'BTC/USDT',
          side: 'buy',
          notionalUsd: 5
        })
      })
      
      if (response.ok) {
        const result = await response.json()
        alert(`Smoke trade submitted: ${result.order_id}`)
      } else {
        const error = await response.json()
        alert(`Smoke trade failed: ${error.detail}`)
      }
    } catch (error) {
      console.error('Error executing smoke trade:', error)
      alert('Smoke trade failed: Network error')
    }
    setIsUpdating(false)
  }

  const handleSilenceAlerts = async (minutes: number) => {
    try {
      const response = await fetch(`${apiBase}/api/alerts/mute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ severity: 'WARN', duration_minutes: minutes })
      })
      
      if (response.ok) {
        alert(`Alerts silenced for ${minutes} minutes`)
      }
    } catch (error) {
      console.error('Failed to silence alerts:', error)
    }
  }

  const handleUnsilenceAlerts = async () => {
    try {
      const response = await fetch(`${apiBase}/api/alerts/unmute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ severity: 'WARN' })
      })
      
      if (response.ok) {
        alert('Alerts unmuted')
      }
    } catch (error) {
      console.error('Failed to unmute alerts:', error)
    }
  }

  const handlePaperTradingConfigUpdate = async () => {
    setIsUpdating(true)
    try {
      const response = await fetch(`${apiBase}/api/config/paper-trading`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          initial_capital: paperTradingConfig.initial_capital,
          max_position_size: paperTradingConfig.max_position_size
        })
      })
      
      if (response.ok) {
        alert('Paper trading configuration updated successfully')
      } else {
        const error = await response.json()
        alert(`Failed to update configuration: ${error.detail}`)
      }
    } catch (error) {
      console.error('Failed to update paper trading config:', error)
      alert('Failed to update configuration: Network error')
    }
    setIsUpdating(false)
  }

  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Risk & Controls</h1>
        <p className="text-muted-foreground">Trading controls and risk management settings</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Shield className="w-5 h-5 mr-2" />
              Bot Controls
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">Current Status</span>
                <Badge variant={riskSettings.botStatus === 'running' ? 'default' : 'secondary'}>
                  {riskSettings.botStatus}
                </Badge>
              </div>
              
              <div className="flex space-x-3">
                <button
                  onClick={handlePause}
                  disabled={isUpdating || riskSettings.botStatus === 'paused'}
                  className="flex-1 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Pause
                </button>
                <button
                  onClick={handleResume}
                  disabled={isUpdating || riskSettings.botStatus === 'running'}
                  className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Resume
                </button>
                <button
                  onClick={handleSmokeTradeTest}
                  disabled={isUpdating || riskSettings.botStatus === 'paused'}
                  className="flex-1 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md transition-colors flex items-center justify-center"
                >
                  <DollarSign className="w-4 h-4 mr-2" />
                  $5 Smoke Test
                </button>
              </div>

              {riskSettings.killSwitchActive && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
                      <span className="text-red-800 font-medium">Kill Switch Active</span>
                    </div>
                    <button
                      onClick={resetKillSwitch}
                      disabled={isUpdating}
                      className="bg-red-600 hover:bg-red-700 text-white text-sm font-medium py-1 px-3 rounded-md transition-colors"
                    >
                      Reset
                    </button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <DollarSign className="w-5 h-5 mr-2" />
              Wallet Balances (Paper)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(walletBalances || []).map((balance) => (
                <div key={balance.currency} className="flex justify-between items-center">
                  <span className="font-medium">{balance.currency}</span>
                  <div className="text-right">
                    <div className="font-medium">{balance.balance.toLocaleString()}</div>
                    <div className="text-sm text-muted-foreground">${balance.usdValue.toLocaleString()}</div>
                  </div>
                </div>
              ))}
              <div className="border-t pt-3 mt-3">
                <div className="flex justify-between items-center font-medium">
                  <span>Total USD Value</span>
                  <span>${(walletBalances || []).reduce((sum, b) => sum + b.usdValue, 0).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center">
            <DollarSign className="w-5 h-5 mr-2" />
            Paper Trading Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Initial Capital (USD)
              </label>
              <input
                type="number"
                step="1000"
                min="1000"
                max="10000000"
                value={paperTradingConfig.initial_capital}
                onChange={(e) => setPaperTradingConfig(prev => ({ ...prev, initial_capital: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Amount of capital to use for paper trading
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Max Position Size (%)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.01"
                max="1.0"
                value={paperTradingConfig.max_position_size}
                onChange={(e) => setPaperTradingConfig(prev => ({ ...prev, max_position_size: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Maximum position size as percentage of capital
              </p>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between">
            <div>
              <Badge variant={paperTradingConfig.mode === 'paper' ? 'default' : 'secondary'}>
                Mode: {paperTradingConfig.mode.toUpperCase()}
              </Badge>
            </div>
            <button
              onClick={handlePaperTradingConfigUpdate}
              disabled={isUpdating}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-6 rounded-md transition-colors"
            >
              {isUpdating ? 'Updating...' : 'Update Configuration'}
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Risk Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Daily Kill Switch (%)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={riskSettings.dailyKillPct}
                onChange={(e) => setRiskSettings(prev => ({ ...prev, dailyKillPct: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-muted-foreground mt-1">Current: {riskSettings.currentDrawdown?.toFixed(2) || '0.00'}%</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Max Position Size (%)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="100"
                value={riskSettings.maxPosPct}
                onChange={(e) => setRiskSettings(prev => ({ ...prev, maxPosPct: parseFloat(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Max Slippage (bps)
              </label>
              <input
                type="number"
                step="1"
                min="0"
                max="100"
                value={riskSettings.maxSlippageBps}
                onChange={(e) => setRiskSettings(prev => ({ ...prev, maxSlippageBps: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={handleRiskUpdate}
              disabled={isUpdating}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-6 rounded-md transition-colors"
            >
              {isUpdating ? 'Updating...' : 'Update Risk Settings'}
            </button>
          </div>

          <div className="space-y-4 mt-6">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium">Maintenance Mode</h4>
                <p className="text-sm text-muted-foreground">
                  Disable trading and gray out controls
                </p>
              </div>
              <button
                onClick={toggleMaintenanceMode}
                className={`px-4 py-2 rounded-md font-medium transition-colors ${
                  maintenanceMode
                    ? 'bg-yellow-600 hover:bg-yellow-700 text-white'
                    : 'bg-gray-600 hover:bg-gray-700 text-white'
                }`}
              >
                {maintenanceMode ? 'Disable Maintenance' : 'Enable Maintenance'}
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Shield className="w-5 h-5 mr-2" />
            Alert Controls
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Silence Alerts</label>
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => handleSilenceAlerts(30)}
                  className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-md transition-colors"
                >
                  Silence 30 min
                </button>
                <button
                  onClick={() => handleSilenceAlerts(60)}
                  className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-md transition-colors"
                >
                  Silence 1 hour
                </button>
                <button
                  onClick={() => handleUnsilenceAlerts()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                >
                  Unmute
                </button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Silences INFO and WARN alerts. CRITICAL alerts still post.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
