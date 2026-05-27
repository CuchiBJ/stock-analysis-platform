'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { API_URL } from '@/lib/utils'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { ExternalLink, ChevronDown, ChevronRight, EyeOff, Eye } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'

interface CriterionStatus {
  passes: boolean
  value?: number
  threshold?: number
  detail?: string
}

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
}

interface EmergingRow {
  symbol: string
  perf_13w: number | null
  perf_4w: number | null
  rs_spy: number
  current_price: number | null
  minervini_status: Record<string, CriterionStatus>
  qualifies_as_emerging_because: string
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
  results: EmergingRow[]
}

interface Props {
  refreshKey: number
}

const CRITERION_LABELS: Record<string, string> = {
  perf_1y_gt_30: 'perf_1y > 30%',
  price_above_ema200: 'price > EMA200',
  price_above_ema50: 'price > EMA50',
  sma50_gt_sma150: 'SMA50 > SMA150',
  sma150_gt_sma200_x_105: 'SMA150 > SMA200 × 1.05',
  range_52w_gte_60pct: '52W range ≥ 60%',
  price_above_low_gte_70pct: 'price above 52W low ≥ 70%',
  adr_gte_3pct: 'ADR ≥ 3%',
}

export default function EmergingLeadersQueue({ refreshKey }: Props) {
  const [response, setResponse] = useState<QueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [viewAnyway, setViewAnyway] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setViewAnyway(false)
    fetch(`${API_URL}/api/v1/queue/emerging-leaders`)
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

  const toggle = (sym: string) => {
    const next = new Set(expanded)
    if (next.has(sym)) next.delete(sym); else next.add(sym)
    setExpanded(next)
  }

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
              <p className="text-sm font-semibold text-amber-300 mb-1">Cola Emerging Leaders suprimida</p>
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
            No emerging leaders right now. Criteria: perf_13w &gt; 20%, RS &gt; 105, price &gt; EMA50/200, but NOT fully Minervini.
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
      {rows.map(r => {
        const isOpen = expanded.has(r.symbol)
        return (
          <Card key={r.symbol} className="p-3">
            <div className="flex items-center justify-between gap-4">
              <div
                className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                onClick={() => toggle(r.symbol)}
              >
                {isOpen ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
                <div className="font-bold text-foreground w-16">{r.symbol}</div>
                {r.group_strength && (
                  <GroupStrengthBadge group={r.group_strength.group} badge={r.group_strength.badge} />
                )}
                <div className="text-xs text-muted-foreground">{r.qualifies_as_emerging_because}</div>
              </div>

              <div className="flex items-center gap-4 text-xs">
                <div>
                  <span className="text-muted-foreground">13w: </span>
                  <span className="font-mono text-green-400">+{r.perf_13w?.toFixed(0)}%</span>
                </div>
                <div>
                  <span className="text-muted-foreground">RS: </span>
                  <span className="font-mono text-foreground">{r.rs_spy.toFixed(0)}</span>
                </div>
                <Link
                  href={`/stock/${r.symbol}`}
                  className="text-primary hover:text-primary/80"
                >
                  detail →
                </Link>
                <a
                  href={r.tradingview_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-primary hover:text-primary/80"
                >
                  TV <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {isOpen && (
              <div className="mt-3 pt-3 border-t border-border grid grid-cols-2 gap-2">
                {Object.entries(r.minervini_status).map(([key, status]) => (
                  <div
                    key={key}
                    className={`text-[10px] px-2 py-1 rounded border ${
                      status.passes
                        ? 'border-green-500/30 bg-green-500/10 text-green-400'
                        : 'border-red-500/30 bg-red-500/10 text-red-400'
                    }`}
                  >
                    <span className="font-mono">{status.passes ? '✓' : '✗'}</span>{' '}
                    {CRITERION_LABELS[key] ?? key}
                    {!status.passes && status.value != null && status.threshold != null && (
                      <span className="ml-1 opacity-75">
                        ({status.value.toFixed(1)} / {status.threshold.toFixed(1)})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )
      })}
    </div>
  )
}
