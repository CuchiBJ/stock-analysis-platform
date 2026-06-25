'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import {
  TrendingUp, TrendingDown, Activity, Clock,
  Eye, Volume2, Minimize2, RefreshCw, Shield, ArrowDown, AlertTriangle, Rocket,
} from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { API_URL, getTimeAgo, getSeverityColor, getSeverityText } from '@/lib/utils'

interface TransitionEvent {
  symbol: string
  transition: string
  direction: string
  strength: number
  observation_priority: number
  pullback_quality_score?: number | null
  setup_score?: number | null
  is_pre_reclaim: boolean
  timestamp: string
  narrative: string
  severity: 'positive' | 'neutral' | 'negative' | 'critical'
  rs_change: number
  volume_change_pct: number
  current_price?: number
  change_pct?: number
  dist_to_setup_pct?: number
  dist_ema_label?: string
}

const TRANSITION_ICON: Record<string, JSX.Element> = {
  // Pre-reclaim (foco del sistema)
  entering_pullback:    <ArrowDown className="w-3 h-3 text-yellow-400" />,
  volume_dry_up:        <Volume2 className="w-3 h-3 text-cyan-400" />,
  compressing:          <Minimize2 className="w-3 h-3 text-purple-400" />,
  flush_and_recover:    <RefreshCw className="w-3 h-3 text-green-300" />,
  support_holding:      <Shield className="w-3 h-3 text-blue-400" />,
  // Pre-breakout (coiling en máximos)
  breakout:             <Rocket className="w-3 h-3 text-green-400" />,
  // Reclaim (existe, no domina)
  reclaiming:           <TrendingUp className="w-3 h-3 text-green-300 opacity-70" />,
  continuation_holding: <Activity className="w-3 h-3 text-green-400" />,
  // Deterioration
  distribution:         <TrendingDown className="w-3 h-3 text-red-400" />,
  failing:              <AlertTriangle className="w-3 h-3 text-red-500" />,
  weakening:            <TrendingDown className="w-3 h-3 text-orange-400" />,
  // Neutral
  stable:               <Activity className="w-3 h-3 text-white/30" />,
  stabilizing:          <Activity className="w-3 h-3 text-blue-400" />,
}

function getIcon(transition: string): JSX.Element {
  return TRANSITION_ICON[transition] ?? <Activity className="w-3 h-3 text-white/30" />
}

// Score unificado de ranking: breakouts traen setup_score; pullbacks caen al
// pullback_quality_score. El Feed ordena best-first por este valor.
function rankScore(event: TransitionEvent): number | null | undefined {
  return event.setup_score ?? event.pullback_quality_score
}

// Quality tier from the rank score — the Feed is ordered best-first, so the
// badge lets you read tradeability at a glance (≥70 fuerte, 55–70 ok, <55 débil).
function qualityTier(score?: number | null): { label: string; cls: string } | null {
  if (score == null) return null
  if (score >= 70) return { label: 'fuerte', cls: 'text-green-400 bg-green-400/10 border-green-400/20' }
  if (score >= 55) return { label: 'ok',     cls: 'text-amber-400 bg-amber-400/10 border-amber-400/20' }
  return { label: 'débil', cls: 'text-red-400 bg-red-400/10 border-red-400/20' }
}

function getRowAccent(event: TransitionEvent): string {
  if (event.is_pre_reclaim && event.observation_priority >= 70)
    return 'border-l-2 border-l-cyan-500'
  if (event.is_pre_reclaim && event.observation_priority >= 50)
    return 'border-l-2 border-l-blue-500'
  if (event.strength >= 0.8)
    return 'border-l-2 border-l-green-500'
  return 'border-l-2 border-l-white/10'
}

export default function LiveTransitionFeed() {
  const [transitions, setTransitions] = useState<TransitionEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { data: wsEvent, isConnected } = useWebSocket<TransitionEvent>({ channel: 'transitions' })
  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const fetchTransitions = useCallback(async () => {
    try {
      setError(null)
      const response = await fetch(`${API_URL}/api/v1/transitions/live?limit=20`)
      if (!response.ok) throw new Error('Failed to load transitions')
      const data = await response.json()
      setTransitions(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load transitions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!wsEvent) return
    setTransitions(prev => {
      const merged = [wsEvent, ...prev.filter(t => t.symbol !== wsEvent.symbol)]
      // Keep quality-first ordering even as live events arrive.
      merged.sort((a, b) => (rankScore(b) ?? 0) - (rankScore(a) ?? 0))
      return merged.slice(0, 50)
    })
  }, [wsEvent])

  useEffect(() => {
    if (metricsEvent?.event === 'updated') fetchTransitions()
  }, [metricsEvent, fetchTransitions])

  useEffect(() => {
    fetchTransitions()
    if (isConnected) return
    const interval = setInterval(fetchTransitions, 30000)
    return () => clearInterval(interval)
  }, [isConnected, fetchTransitions])

  if (loading) {
    return (
      <Card blockType="live-transitions" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Setup Feed
          </h3>
        </div>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => <LoadingSkeleton key={i} variant="card" />)}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card blockType="live-transitions" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
          Setup Feed
        </h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!transitions || transitions.length === 0) {
    return (
      <Card blockType="live-transitions" className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
          Setup Feed
        </h3>
        <p className="text-muted-foreground text-sm">No transitions detected</p>
      </Card>
    )
  }

  return (
    <Card blockType="live-transitions" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Setup Feed
        </h3>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full animate-pulse ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
          <span className="text-xs text-muted-foreground">{isConnected ? 'WS Live' : 'Polling'}</span>
        </div>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {transitions.map((event, index) => {
          const qt = qualityTier(rankScore(event))
          return (
          <Link
            key={`${event.symbol}-${index}`}
            href={`/stock/${event.symbol}`}
            className={`block p-3 rounded ${getSeverityColor(event.severity)} ${getRowAccent(event)} transition-all hover:opacity-90`}
            style={{ opacity: (index >= 8 && event.transition !== 'breakout') ? 0.4 : 1 }}
          >
            {/* Row 1: symbol + badges + price context + time */}
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-bold text-sm">{event.symbol}</span>

                {/* WATCH badge — pre-reclaim candidate */}
                {event.is_pre_reclaim && (
                  <span className="text-[9px] px-1 py-0.5 rounded border
                    border-cyan-400/30 bg-cyan-400/10 text-cyan-400
                    uppercase tracking-wide shrink-0">
                    watch
                  </span>
                )}

                <span className={`text-[10px] px-1.5 py-0.5 rounded ${getSeverityText(event.severity)} uppercase`}>
                  {event.transition}
                </span>

                {/* Quality badge — Feed is ordered best-first by setup quality */}
                {qt && (
                  <span
                    className={`text-[9px] px-1 py-0.5 rounded border ${qt.cls} uppercase tracking-wide shrink-0`}
                    title={`${event.transition === 'breakout' ? 'Breakout' : 'Pullback'} quality ${rankScore(event)?.toFixed(0)}/100`}
                  >
                    {qt.label}
                  </span>
                )}

                {/* Price context — inline */}
                {event.current_price != null && (
                  <span className="text-[10px] font-mono text-foreground/80">
                    ${event.current_price.toFixed(2)}
                  </span>
                )}
                {event.change_pct != null && (
                  <span className={`text-[10px] font-mono ${event.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {event.change_pct >= 0 ? '+' : ''}{event.change_pct.toFixed(1)}%
                  </span>
                )}
                {event.dist_to_setup_pct != null && (
                  <span className="text-[10px] text-muted-foreground">
                    {event.dist_to_setup_pct > 0 ? '+' : ''}{event.dist_to_setup_pct.toFixed(1)}% {event.dist_ema_label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 text-muted-foreground shrink-0">
                <Clock className="w-3 h-3" />
                <span className="text-[10px]">{getTimeAgo(event.timestamp)}</span>
              </div>
            </div>

            {/* Row 2: narrative */}
            <p className="text-xs text-muted-foreground mb-1.5">{event.narrative}</p>

            {/* Row 3: metrics */}
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1">
                {getIcon(event.transition)}
                <span>Str: {(event.strength * 100).toFixed(0)}%</span>
              </div>
              {event.is_pre_reclaim && (
                <span className="text-cyan-400/70">
                  Obs: {event.observation_priority.toFixed(0)}
                </span>
              )}
              {event.rs_change !== 0 && (
                <span>RS: {event.rs_change > 0 ? '+' : ''}{event.rs_change.toFixed(1)}</span>
              )}
              {Math.abs(event.volume_change_pct) > 10 && (
                <span>Vol: {event.volume_change_pct > 0 ? '+' : ''}{event.volume_change_pct.toFixed(0)}%</span>
              )}
            </div>
          </Link>
          )
        })}
      </div>
    </Card>
  )
}
