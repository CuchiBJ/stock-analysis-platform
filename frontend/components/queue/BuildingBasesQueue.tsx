'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/utils'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { ExternalLink } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'
import TakeFromQueueButton from '@/components/queue/TakeFromQueueButton'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
}

interface BaseRow {
  symbol: string
  vcp_score: number
  weeks_in_base: number
  atr_range_last_20d: number
  current_distance_to_ema21_atr: number | null
  volume_contraction_trend: string
  tradingview_url: string
  market_group?: string | null
  group_strength?: GroupStrength | null
}

interface ContextSnapshot {
  participation: string
  leadership: string
}

interface QueueResponse {
  suppressed: boolean
  suppression_reason: string | null
  context_snapshot: ContextSnapshot
  results: BaseRow[]
}

interface Props {
  refreshKey: number
}

function trendColor(t: string) {
  if (t === 'declining') return 'text-green-400'
  if (t === 'mild') return 'text-yellow-400'
  return 'text-muted-foreground'
}

function tightnessColor(r: number) {
  if (r < 1.0) return 'text-green-400'
  if (r < 1.5) return 'text-yellow-400'
  return 'text-orange-400'
}

export default function BuildingBasesQueue({ refreshKey }: Props) {
  const [response, setResponse] = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/queue/building-bases`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) return
        setResponse(data)
        setError(null)
      })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  if (loading) return <div className="space-y-2">{[...Array(4)].map((_, i) => <LoadingSkeleton key={i} variant="card" />)}</div>
  if (error) return <p className="text-sm text-destructive">Error: {error}</p>
  if (!response) return null

  const { results: rows } = response

  if (rows.length === 0) {
    return (
      <div className="space-y-2">
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            No tight VCP bases right now. Criteria: Minervini leader + VCP ≥ 70 + 6+ weeks in base + ATR oscillation ≤ 2.0 over 20 days.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {rows.map(r => (
        <Card key={r.symbol} className="p-3 hover:bg-muted/30 cursor-pointer transition-colors">
          <div className="flex items-center justify-between gap-4">
            <Link href={`/stock/${r.symbol}`} className="flex items-center gap-3 min-w-0 flex-1">
              <div className="font-bold text-foreground w-16">{r.symbol}</div>
              {r.group_strength && (
                <GroupStrengthBadge group={r.group_strength.group} badge={r.group_strength.badge} />
              )}
              <div className="text-xs text-muted-foreground">{r.weeks_in_base}w base</div>
              <div className={`text-xs ${trendColor(r.volume_contraction_trend)}`}>
                vol {r.volume_contraction_trend}
              </div>
            </Link>

            <div className="flex items-center gap-4 text-xs">
              <div>
                <span className="text-muted-foreground">VCP: </span>
                <span className="font-mono text-foreground">{r.vcp_score.toFixed(0)}</span>
              </div>
              <div>
                <span className="text-muted-foreground">ATR range 20d: </span>
                <span className={`font-mono ${tightnessColor(r.atr_range_last_20d)}`}>
                  {r.atr_range_last_20d.toFixed(2)}
                </span>
              </div>
              {r.current_distance_to_ema21_atr != null && (
                <div>
                  <span className="text-muted-foreground">EMA21: </span>
                  <span className="font-mono text-foreground">
                    {r.current_distance_to_ema21_atr >= 0 ? '+' : ''}{r.current_distance_to_ema21_atr.toFixed(2)} ATR
                  </span>
                </div>
              )}
              <a
                href={r.tradingview_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={e => e.stopPropagation()}
                className="flex items-center gap-1 text-primary hover:text-primary/80"
              >
                TV <ExternalLink className="w-3 h-3" />
              </a>
              <TakeFromQueueButton symbol={r.symbol} setup="building_base" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
