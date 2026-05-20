'use client'

import { useEffect, useState, useRef } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { TrendingUp, TrendingDown, Activity, Clock } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { API_URL, getTimeAgo, getSeverityColor, getSeverityText } from '@/lib/utils'

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

  // WebSocket for real-time pushes
  const { data: wsEvent, isConnected } = useWebSocket<TransitionEvent>({ channel: 'transitions' })

  // When a new event arrives via WebSocket, prepend it
  useEffect(() => {
    if (!wsEvent) return
    setTransitions(prev => {
      const next = [wsEvent, ...prev.filter(t => t.symbol !== wsEvent.symbol)]
      return next.slice(0, 50)
    })
  }, [wsEvent])

  // REST polling — only when WebSocket is not connected (fallback)
  useEffect(() => {
    const fetchTransitions = async () => {
      try {
        setError(null)
        const response = await fetch(`${API_URL}/api/v1/transitions/live?limit=20`)
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

    fetchTransitions() // always fetch once on mount for initial data
    if (isConnected) return // WS active — no polling needed
    const interval = setInterval(fetchTransitions, 30000)
    return () => clearInterval(interval)
  }, [isConnected])

  const getTransitionIcon = (transition: string) => {
    if (transition === 'improving' || transition === 'tightening' || transition === 'reclaiming') {
      return <TrendingUp className="w-3 h-3" />
    } else if (transition === 'weakening' || transition === 'failing') {
      return <TrendingDown className="w-3 h-3" />
    } else {
      return <Activity className="w-3 h-3" />
    }
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
          <div className={`w-2 h-2 rounded-full animate-pulse ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
          <span className="text-xs text-muted-foreground">{isConnected ? 'WS Live' : 'Polling'}</span>
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
