'use client'

import { useEffect, useState } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { TrendingUp, TrendingDown, Activity, Clock } from 'lucide-react'

interface TransitionEvent {
  symbol: string
  transition: string
  direction: string
  strength: number
  timestamp: string
  narrative: string
  severity: 'positive' | 'neutral' | 'negative' | 'critical'
  rs_change: number
  volume_change_pct: number
}

export default function LiveTransitionFeed() {
  const [transitions, setTransitions] = useState<TransitionEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTransitions = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await fetch('http://localhost:8000/api/v1/transitions/live?limit=10')
        if (!response.ok) throw new Error('Failed to load transitions')
        const data = await response.json()
        setTransitions(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load transitions')
        console.error('Error loading transitions:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchTransitions()
    // Refresh every 30 seconds for live feel
    const interval = setInterval(fetchTransitions, 30000)
    return () => clearInterval(interval)
  }, [])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'positive': return 'bg-green-500/20 border-green-500/30'
      case 'neutral': return 'bg-blue-500/20 border-blue-500/30'
      case 'negative': return 'bg-orange-500/20 border-orange-500/30'
      case 'critical': return 'bg-red-500/20 border-red-500/30'
      default: return 'bg-slate-500/20 border-slate-500/30'
    }
  }

  const getSeverityText = (severity: string) => {
    switch (severity) {
      case 'positive': return 'text-green-400'
      case 'neutral': return 'text-blue-400'
      case 'negative': return 'text-orange-400'
      case 'critical': return 'text-red-400'
      default: return 'text-slate-400'
    }
  }

  const getTransitionIcon = (transition: string) => {
    if (transition === 'improving' || transition === 'tightening' || transition === 'reclaiming') {
      return <TrendingUp className="w-3 h-3" />
    } else if (transition === 'weakening' || transition === 'failing') {
      return <TrendingDown className="w-3 h-3" />
    } else {
      return <Activity className="w-3 h-3" />
    }
  }

  const getTimeAgo = (timestamp: string) => {
    const now = new Date()
    const then = new Date(timestamp)
    const diffMs = now.getTime() - then.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    return `${Math.floor(diffHours / 24)}d ago`
  }

  if (loading) {
    return (
      <Card blockType="live-transitions" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Live Transitions</h3>
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
      <Card blockType="live-transitions" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Live Transitions</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!transitions || transitions.length === 0) {
    return (
      <Card blockType="live-transitions" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Live Transitions</h3>
        <p className="text-muted-foreground text-sm">No recent transitions</p>
      </Card>
    )
  }

  return (
    <Card blockType="live-transitions" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Live Transitions</h3>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-muted-foreground">Live</span>
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {transitions.map((event, index) => (
          <div
            key={`${event.symbol}-${index}`}
            className={`p-3 rounded border ${getSeverityColor(event.severity)} transition-all hover:opacity-80`}
            style={{
              opacity: index >= 5 ? 0.3 : 1, // Fade older events
            }}
          >
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm">{event.symbol}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${getSeverityText(event.severity)} uppercase`}>
                  {event.transition}
                </span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                <Clock className="w-3 h-3" />
                <span className="text-[10px]">{getTimeAgo(event.timestamp)}</span>
              </div>
            </div>

            <p className="text-xs text-muted-foreground mb-1">{event.narrative}</p>

            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1">
                {getTransitionIcon(event.transition)}
                <span>Strength: {(event.strength * 100).toFixed(0)}%</span>
              </div>
              {event.rs_change !== 0 && (
                <span>RS: {event.rs_change > 0 ? '+' : ''}{event.rs_change.toFixed(1)}</span>
              )}
              {event.volume_change_pct !== 0 && (
                <span>Vol: {event.volume_change_pct > 0 ? '+' : ''}{event.volume_change_pct.toFixed(0)}%</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
