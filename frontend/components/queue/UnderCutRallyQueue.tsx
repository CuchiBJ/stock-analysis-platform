'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/utils'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { ExternalLink, EyeOff, Eye } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
}

interface UnRRow {
  symbol: string
  transition_type: string
  event_age_days: number
  distance_to_ema21_atr: number
  rs_spy: number | null
  volume_contraction: number | null
  touches_last_30d: number
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
  results: UnRRow[]
}

interface Props {
  refreshKey: number
}

function transitionLabel(t: string) {
  return t.replace(/_/g, ' ').toUpperCase()
}

function ageLabel(d: number) {
  return d === 0 ? 'today' : d === 1 ? '1d ago' : `${d}d ago`
}

export default function UnderCutRallyQueue({ refreshKey }: Props) {
  const [response, setResponse] = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewAnyway, setViewAnyway] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setViewAnyway(false)
    fetch(`${API_URL}/api/v1/queue/u-and-r`)
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

  const { suppressed, suppression_reason, results: rows } = response

  if (suppressed && !viewAnyway) {
    return (
      <div className="space-y-2">
        <Card className="p-5 border-amber-400/30 bg-amber-400/5">
          <div className="flex items-start gap-3">
            <EyeOff className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-amber-300 mb-1">Cola U&amp;R suprimida</p>
              {suppression_reason && (
                <p className="text-xs text-white/60 mb-3">{suppression_reason}</p>
              )}
              <button
                className="text-xs text-white/50 hover:text-white/80 flex items-center gap-1 transition-colors"
                onClick={() => setViewAnyway(true)}
              >
                <Eye className="w-3 h-3" /> Ver de todas formas
              </button>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="space-y-2">
        {suppressed && viewAnyway && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-amber-400/20 bg-amber-400/5 mb-1">
            <EyeOff className="w-3 h-3 text-amber-400" />
            <span className="text-[10px] text-amber-300">Esta lens está suprimida por contexto de mercado</span>
          </div>
        )}
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            No qualifying setups in the last 2 days. The system tracks forward — wait for the next SLOW cycle.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {suppressed && viewAnyway && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-amber-400/20 bg-amber-400/5">
          <EyeOff className="w-3 h-3 text-amber-400" />
          <span className="text-[10px] text-amber-300">Esta lens está suprimida por contexto de mercado</span>
        </div>
      )}
      {rows.map(r => (
        <Card
          key={r.symbol}
          className="p-3 hover:bg-muted/30 cursor-pointer transition-colors"
        >
          <div className="flex items-center justify-between gap-4">
            <Link href={`/stock/${r.symbol}`} className="flex items-center gap-3 min-w-0 flex-1">
              <div className="font-bold text-foreground w-16">{r.symbol}</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
                {transitionLabel(r.transition_type)}
              </div>
              {r.group_strength && (
                <GroupStrengthBadge group={r.group_strength.group} badge={r.group_strength.badge} />
              )}
              <div className="text-xs text-muted-foreground">{ageLabel(r.event_age_days)}</div>
            </Link>

            <div className="flex items-center gap-4 text-xs">
              <div>
                <span className="text-muted-foreground">EMA21: </span>
                <span className="font-mono text-foreground">
                  {r.distance_to_ema21_atr >= 0 ? '+' : ''}{r.distance_to_ema21_atr.toFixed(2)} ATR
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">RS: </span>
                <span className="font-mono text-foreground">{r.rs_spy?.toFixed(0) ?? '—'}</span>
              </div>
              {r.volume_contraction != null && (
                <div>
                  <span className="text-muted-foreground">Vol: </span>
                  <span className="font-mono text-foreground">-{r.volume_contraction.toFixed(0)}%</span>
                </div>
              )}
              <div>
                <span className="text-muted-foreground">Toques 30d: </span>
                <span className="font-mono text-foreground">{r.touches_last_30d}</span>
              </div>
              <a
                href={r.tradingview_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={e => e.stopPropagation()}
                className="flex items-center gap-1 text-primary hover:text-primary/80"
              >
                TV <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}
