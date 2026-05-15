'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api/client'
import Card from '@/components/base/Card'
import { ArrowUp, ArrowDown, Activity, TrendingUp, AlertTriangle } from 'lucide-react'

interface MarketState {
  risk_on: boolean
  breadth_quality: 'strong' | 'moderate' | 'weak'
  sector_leadership: string
  momentum_health: 'healthy' | 'neutral' | 'weak'
  participation_quality: 'strong' | 'moderate' | 'narrow'
  rotation_quality: 'active' | 'stable' | 'stagnant'
  insight: string
}

export default function MarketStatePanel() {
  const [state, setState] = useState<MarketState | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchState = async () => {
      try {
        setLoading(true)
        // For now, use mock data - will replace with real API call
        const mockState: MarketState = {
          risk_on: true,
          breadth_quality: 'strong',
          sector_leadership: 'Technology',
          momentum_health: 'healthy',
          participation_quality: 'strong',
          rotation_quality: 'active',
          insight: 'Risk ON with broad participation led by Technology'
        }
        setState(mockState)
      } catch (error) {
        console.error('Error fetching market state:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchState()
    // Refresh every 60 seconds
    const interval = setInterval(fetchState, 60000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card className="p-4">
        <div className="animate-pulse h-12 bg-muted rounded" />
      </Card>
    )
  }

  if (!state) return null

  const getRiskBadge = () => {
    if (state.risk_on) {
      return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-full">
          <Activity className="w-4 h-4 text-green-500" />
          <span className="text-green-500 font-semibold text-sm">Risk ON</span>
        </div>
      )
    }
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/20 rounded-full">
        <Activity className="w-4 h-4 text-red-500" />
        <span className="text-red-500 font-semibold text-sm">Risk OFF</span>
      </div>
    )
  }

  const getQualityColor = (quality: string) => {
    switch (quality) {
      case 'strong':
      case 'healthy':
      case 'active':
        return 'text-green-400'
      case 'moderate':
      case 'neutral':
      case 'stable':
        return 'text-yellow-400'
      case 'weak':
      case 'narrow':
      case 'stagnant':
        return 'text-red-400'
      default:
        return 'text-muted-foreground'
    }
  }

  const getQualityIcon = (quality: string) => {
    if (quality === 'strong' || quality === 'healthy' || quality === 'active') {
      return <TrendingUp className="w-4 h-4 text-green-400" />
    }
    if (quality === 'weak' || quality === 'narrow' || quality === 'stagnant') {
      return <AlertTriangle className="w-4 h-4 text-red-400" />
    }
    return <Activity className="w-4 h-4 text-yellow-400" />
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        {/* Left: Risk Badge */}
        {getRiskBadge()}

        {/* Center: Key Metrics */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Breadth</span>
            <span className={`text-sm font-semibold ${getQualityColor(state.breadth_quality)}`}>
              {state.breadth_quality}
            </span>
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Leadership</span>
            <span className="text-sm font-semibold text-white">{state.sector_leadership}</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Participation</span>
            <span className={`text-sm font-semibold ${getQualityColor(state.participation_quality)}`}>
              {state.participation_quality}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wide">Rotation</span>
            <span className={`text-sm font-semibold ${getQualityColor(state.rotation_quality)}`}>
              {state.rotation_quality}
            </span>
          </div>
        </div>

        {/* Right: Insight */}
        <div className="flex items-center gap-2 px-4 py-2 bg-muted/30 rounded-lg border border-border">
          {getQualityIcon(state.momentum_health)}
          <span className="text-sm text-white font-medium">{state.insight}</span>
        </div>
      </div>
    </Card>
  )
}
