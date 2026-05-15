'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api/client'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { TrendingUp, TrendingDown, Activity, Flame, Zap, ArrowUp, ArrowDown, Minus } from 'lucide-react'

interface CapitalFlowData {
  sector: string
  flow: 'inflow' | 'outflow' | 'neutral'
  strength: 'strong' | 'moderate' | 'weak'
  change_pct: number
  rvol: number
  acceleration: 'accelerating' | 'decelerating' | 'stable'
  leaders: string[]
}

export default function CapitalFlowPanel() {
  const [data, setData] = useState<CapitalFlowData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await apiClient.get<CapitalFlowData[]>('/capital-flow', { cache: true })
        setData(response)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load capital flow data')
        console.error('Error loading capital flow data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  const getFlowColor = (flow: string) => {
    switch (flow) {
      case 'inflow': return 'text-green-400'
      case 'outflow': return 'text-red-400'
      default: return 'text-muted-foreground'
    }
  }

  const getFlowIcon = (flow: string) => {
    switch (flow) {
      case 'inflow': return <TrendingUp className="w-4 h-4" />
      case 'outflow': return <TrendingDown className="w-4 h-4" />
      default: return <Activity className="w-4 h-4" />
    }
  }

  const getStrengthBadge = (strength: string) => {
    switch (strength) {
      case 'strong': return 'bg-green-500/20 text-green-400 border-green-500/30'
      case 'moderate': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'weak': return 'bg-muted text-muted-foreground border-border'
      default: return 'bg-muted text-muted-foreground border-border'
    }
  }

  const getAccelerationIcon = (acc: string) => {
    switch (acc) {
      case 'accelerating': return <Flame className="w-3 h-3 text-orange-400" />
      case 'decelerating': return <ArrowDown className="w-3 h-3 text-red-400" />
      default: return <Minus className="w-3 h-3 text-muted-foreground" />
    }
  }

  const getRVOLColor = (rvol: number) => {
    if (rvol >= 2) return 'text-green-400'
    if (rvol >= 1.5) return 'text-yellow-400'
    return 'text-muted-foreground'
  }

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Capital Flow</h3>
        </div>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Capital Flow</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Capital Flow</h3>
        <p className="text-muted-foreground text-sm">No capital flow data available</p>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Capital Flow</h3>
        <span className="text-xs text-muted-foreground">{data.length} sectors</span>
      </div>

      <div className="space-y-2">
        {data.map((sector, index) => (
          <div
            key={sector.sector}
            className="flex items-center gap-3 p-3 rounded-lg border border-border/50 hover:bg-muted/50 transition-colors group"
          >
            {/* Flow Icon */}
            <div className={`p-2 rounded-lg ${sector.flow === 'inflow' ? 'bg-green-500/10' : sector.flow === 'outflow' ? 'bg-red-500/10' : 'bg-muted'}`}>
              {getFlowIcon(sector.flow)}
            </div>

            {/* Sector Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-white text-sm">{sector.sector}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${getStrengthBadge(sector.strength)}`}>
                  {sector.strength}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-mono ${getFlowColor(sector.flow)}`}>
                  {sector.change_pct > 0 ? '+' : ''}{sector.change_pct.toFixed(2)}%
                </span>
                <span className={`text-xs font-mono ${getRVOLColor(sector.rvol)}`}>
                  RVOL {sector.rvol.toFixed(1)}x
                </span>
                <div className="flex items-center gap-1">
                  {getAccelerationIcon(sector.acceleration)}
                  <span className="text-[10px] text-muted-foreground">{sector.acceleration}</span>
                </div>
              </div>
            </div>

            {/* Leaders */}
            <div className="flex items-center gap-1">
              {sector.leaders.map((leader) => (
                <span
                  key={leader}
                  className="px-2 py-1 bg-muted/50 rounded text-[10px] font-mono text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors"
                >
                  {leader}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
