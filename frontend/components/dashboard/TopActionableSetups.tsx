'use client'

import { useEffect, useState, useCallback } from 'react'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import CompactSetupCard from './CompactSetupCard'
import { Flame } from 'lucide-react'
import { formatPctChange, API_URL } from '@/lib/utils'
import { useWebSocket } from '@/hooks/useWebSocket'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
  multiplier?: number
}

interface ActionableSetup {
  symbol: string
  priority_score: number
  continuation_prob: number
  probability_source?: 'empirical' | 'rule_based'
  sample_size?: number
  narrative: string
  setup_type: 'ema9_pullback' | 'ema21_pullback'
  pullback_quality: number
  distance_to_ema21: number
  distance_to_ema9: number
  rs_spy: number
  volume_contraction: number
  days_in_state: number
  current_price?: number
  change_pct?: number
  dist_to_setup_pct?: number
  context_warnings?: string[]
  group_strength?: GroupStrength | null
}

interface ActionableEnvelope {
  setups: ActionableSetup[]
}

export default function TopActionableSetups() {
  const [setups, setSetups] = useState<ActionableSetup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Refresh when the scheduler signals new metrics are ready
  const { data: metricsEvent } = useWebSocket<{ event: string }>({ channel: 'metrics' })

  const fetchSetups = useCallback(async () => {
    try {
      setError(null)
      const response = await fetch(`${API_URL}/api/v1/transitions/actionable?limit=6`)
      if (!response.ok) throw new Error('Failed to load actionable setups')
      const data: ActionableEnvelope = await response.json()
      setSetups(data.setups ?? [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load actionable setups')
      console.error('Error loading actionable setups:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Refresh when metrics are updated via WebSocket
  useEffect(() => {
    if (metricsEvent?.event === 'updated') fetchSetups()
  }, [metricsEvent, fetchSetups])

  useEffect(() => {
    fetchSetups()
    const interval = setInterval(fetchSetups, 60000)
    return () => clearInterval(interval)
  }, [fetchSetups])

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Top Actionable Setups</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {[...Array(6)].map((_, i) => (
            <LoadingSkeleton key={i} variant="card" />
          ))}
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Top Actionable Setups</h3>
        <p className="text-red-500 text-sm">Error: {error}</p>
      </Card>
    )
  }

  if (!setups || setups.length === 0) {
    return (
      <Card className="p-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">Top Actionable Setups</h3>
        <p className="text-muted-foreground text-sm">No actionable setups found</p>
      </Card>
    )
  }

  return (
    <Card blockType="actionable" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Top Actionable Setups</h3>
          <Flame className="w-4 h-4 text-orange-400" />
        </div>
        <span className="text-xs text-muted-foreground">{setups.length} setups</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {setups.map((setup, index) => {
          const isEma9 = setup.setup_type === 'ema9_pullback'
          const emaDist = isEma9 ? setup.distance_to_ema9 : setup.distance_to_ema21
          const emaLabel = isEma9 ? 'EMA9' : 'EMA21'
          // ATR-normalized value — format as e.g. "-0.13 ATR" not a pct
          const emaValue = emaDist != null ? `${emaDist >= 0 ? '+' : ''}${emaDist.toFixed(2)}%` : 'N/A'

          const days = setup.days_in_state ?? 1
          const freshness =
            days <= 3  ? 'fresh' :
            days <= 7  ? 'aging' :
            days <= 14 ? 'late-stage' :
            days <= 20 ? 'stale' : 'extended'

          const priceLabel = setup.current_price != null
            ? `$${setup.current_price.toFixed(2)}${setup.change_pct != null ? ` ${setup.change_pct >= 0 ? '+' : ''}${setup.change_pct.toFixed(1)}%` : ''}`
            : null

          return (
            <CompactSetupCard
              key={setup.symbol}
              symbol={setup.symbol}
              priceLabel={priceLabel}
              state={isEma9 ? 'EMA9 Pullback' : 'EMA21 Pullback'}
              transition="stable"
              transitionStrength={setup.priority_score}
              narrative={setup.narrative}
              confidence={setup.priority_score}
              continuationProb={setup.continuation_prob}
              probabilitySource={setup.probability_source}
              sampleSize={setup.sample_size}
              contextWarnings={setup.context_warnings}
              freshness={freshness}
              daysInState={days}
              keyMetrics={{
                ema21: `${emaLabel} ${emaValue}`,
                rs: setup.rs_spy ?? 0,
                volume: setup.volume_contraction ? `-${setup.volume_contraction.toFixed(0)}%` : 'N/A',
              }}
              isPriority={index === 0}
              groupStrength={setup.group_strength}
            />
          )
        })}
      </div>
    </Card>
  )
}
