'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api/client'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { TrendingUp, TrendingDown, Activity, AlertTriangle, CheckCircle } from 'lucide-react'

interface BreadthData {
  above_ema: {
    above_ema20: number
    above_ema50: number
  }
  new_highs_lows: {
    new_highs: number
    new_lows: number
  }
  advance_decline: {
    advancers: number
    decliners: number
    ratio: number
  }
}

export default function BreadthPanel() {
  const [data, setData] = useState<BreadthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await apiClient.get<BreadthData>('/breadth', { cache: true })
        setData(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load breadth data')
        console.error('Error loading breadth data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  const getInsight = () => {
    if (!data) return null

    const above_ema20 = data.above_ema?.above_ema20 || 0
    const new_highs = data.new_highs_lows?.new_highs || 0
    const new_lows = data.new_highs_lows?.new_lows || 0
    const advancers = data.advance_decline?.advancers || 0
    const decliners = data.advance_decline?.decliners || 0
    const adRatio = advancers / (decliners || 1)

    if (above_ema20 > 70 && adRatio > 2) {
      return { text: 'Broad participation with strong momentum', type: 'strong', icon: CheckCircle }
    }
    if (above_ema20 > 60 && new_highs > new_lows * 2) {
      return { text: 'Healthy breadth, leadership emerging', type: 'good', icon: TrendingUp }
    }
    if (above_ema20 < 40 && new_lows > new_highs * 2) {
      return { text: 'Weak breadth, defensive positioning', type: 'weak', icon: AlertTriangle }
    }
    if (above_ema20 < 50 && adRatio < 0.5) {
      return { text: 'Narrow rally, selective leadership', type: 'narrow', icon: Activity }
    }
    if (above_ema20 > 50 && adRatio < 1) {
      return { text: 'Mixed signals, rotation detected', type: 'mixed', icon: Activity }
    }
    return { text: 'Neutral market conditions', type: 'neutral', icon: Activity }
  }

  const getGaugeColor = (value: number) => {
    if (value >= 70) return 'text-green-400'
    if (value >= 50) return 'text-green-300'
    if (value >= 30) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getGaugeWidth = (value: number) => {
    return `${Math.min(Math.max(value, 0), 100)}%`
  }

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Market Breadth</h3>
        </div>
        <div className="space-y-3">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Market Breadth</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Market Breadth</h3>
        <p className="text-muted-foreground text-sm">No breadth data available</p>
      </Card>
    )
  }

  const insight = getInsight()

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Market Breadth</h3>
        {insight && (
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${insight.type === 'strong' || insight.type === 'good'
            ? 'bg-green-500/10 border-green-500/30 text-green-400'
            : insight.type === 'weak' || insight.type === 'narrow'
              ? 'bg-red-500/10 border-red-500/30 text-red-400'
              : 'bg-muted border-border text-muted-foreground'
            }`}>
            {insight.type === 'strong' && <CheckCircle className="w-3 h-3" />}
            {insight.type === 'good' && <TrendingUp className="w-3 h-3" />}
            {insight.type === 'weak' && <AlertTriangle className="w-3 h-3" />}
            {insight.type === 'narrow' && <Activity className="w-3 h-3" />}
            {insight.type === 'mixed' && <Activity className="w-3 h-3" />}
            {insight.type === 'neutral' && <Activity className="w-3 h-3" />}
            <span className="text-[10px] font-medium">{insight.text}</span>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {/* Above EMA20 Gauge */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">Above EMA20</span>
            <span className={`text-sm font-semibold ${getGaugeColor(data.above_ema?.above_ema20 || 0)}`}>
              {data.above_ema?.above_ema20 ? data.above_ema.above_ema20.toFixed(1) + '%' : 'N/A'}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${(data.above_ema?.above_ema20 || 0) >= 50 ? 'bg-green-500' : 'bg-red-500'
                }`}
              style={{ width: getGaugeWidth(data.above_ema?.above_ema20 || 0) }}
            />
          </div>
        </div>

        {/* Above EMA50 Gauge */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">Above EMA50</span>
            <span className={`text-sm font-semibold ${getGaugeColor(data.above_ema?.above_ema50 || 0)}`}>
              {data.above_ema?.above_ema50 ? data.above_ema.above_ema50.toFixed(1) + '%' : 'N/A'}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${(data.above_ema?.above_ema50 || 0) >= 50 ? 'bg-green-500' : 'bg-red-500'
                }`}
              style={{ width: getGaugeWidth(data.above_ema?.above_ema50 || 0) }}
            />
          </div>
        </div>

        {/* New Highs/Lows */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-muted/30 rounded p-3 border border-border/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">New Highs</span>
              <TrendingUp className="w-3 h-3 text-green-400" />
            </div>
            <div className="text-lg font-bold text-green-400">{data.new_highs_lows?.new_highs || 0}</div>
          </div>
          <div className="bg-muted/30 rounded p-3 border border-border/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">New Lows</span>
              <TrendingDown className="w-3 h-3 text-red-400" />
            </div>
            <div className="text-lg font-bold text-red-400">{data.new_highs_lows?.new_lows || 0}</div>
          </div>
        </div>

        {/* Advancers/Decliners */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-green-500/10 rounded p-3 border border-green-500/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Advancers</span>
              <TrendingUp className="w-3 h-3 text-green-400" />
            </div>
            <div className="text-lg font-bold text-green-400">{data.advance_decline?.advancers || 0}</div>
          </div>
          <div className="bg-red-500/10 rounded p-3 border border-red-500/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Decliners</span>
              <TrendingDown className="w-3 h-3 text-red-400" />
            </div>
            <div className="text-lg font-bold text-red-400">{data.advance_decline?.decliners || 0}</div>
          </div>
        </div>
      </div>
    </Card>
  )
}
