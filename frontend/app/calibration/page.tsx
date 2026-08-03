'use client'

import { useEffect, useMemo, useState } from 'react'
import { API_URL } from '@/lib/utils'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { AlertTriangle, CheckCircle2, CircleDashed, Eye, TrendingDown, TrendingUp } from 'lucide-react'

type CohortStatus = 'empirical' | 'insufficient' | 'no_data'
type Drift = 'deteriorating' | 'stable' | 'improving' | 'insufficient'

interface ConfidenceInterval {
  low: number
  high: number
}

interface CalibrationCohort {
  n_observed: number
  n_settled: number
  n_resolved: number
  n_pending: number
  success_count: number
  failure_count: number
  neutral_count: number
  success_rate: number | null
  delivery_rate: number | null
  confidence_interval: ConfidenceInterval | null
  status: CohortStatus
  samples_needed: number
}

interface CalibrationRow {
  transition_type: string
  bullish: boolean
  historical: CalibrationCohort
  recent: CalibrationCohort
  baseline: CalibrationCohort
  current_regime: CalibrationCohort
  drift: Drift
  recent_delta_pp: number | null
  regime_delta_pp: number | null
}

interface FollowThroughContext {
  descriptor: 'PAYING' | 'MIXED' | 'NOT_PAYING' | 'UNKNOWN'
  basis: string
  window_days: number
  delivery_rate: number | null
  baseline_rate: number | null
  resolved: number
  pending: number
}

interface CalibrationResponse {
  min_samples_required: number
  recent_window_days: number
  as_of: string
  current_context: {
    regime: string
    regime_confidence: number
    follow_through: FollowThroughContext | null
    posture: { state: string; instruction: string } | null
  }
  total_observations: number
  total_resolved: number
  total_settled: number
  total_pending: number
  eta_first_data: string | null
  rows: CalibrationRow[]
}

const driftOrder: Record<Drift, number> = {
  deteriorating: 0,
  stable: 1,
  improving: 2,
  insufficient: 3,
}

function formatPct(value: number | null): string {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function formatRegime(value: string): string {
  return value.replaceAll('_', ' ').toUpperCase()
}

function CohortValue({ cohort, minSamples }: { cohort: CalibrationCohort; minSamples: number }) {
  if (cohort.status === 'no_data') {
    return <span className="text-white/30">sin data</span>
  }
  if (cohort.status === 'insufficient') {
    return (
      <span className="text-amber-400/80" title={`Se requieren ${minSamples} outcomes settled`}>
        {cohort.n_settled} / {minSamples}
      </span>
    )
  }
  const interval = cohort.confidence_interval
  return (
    <span
      className="text-foreground"
      title={interval ? `95% CI ${(interval.low * 100).toFixed(1)}–${(interval.high * 100).toFixed(1)}% · ${cohort.n_settled} settled` : undefined}
    >
      {formatPct(cohort.delivery_rate)}
    </span>
  )
}

function DriftBadge({ drift, delta }: { drift: Drift; delta: number | null }) {
  if (drift === 'deteriorating') {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-400">
        <TrendingDown className="h-3 w-3" /> deteriorating {delta != null ? `${delta.toFixed(1)}pp` : ''}
      </span>
    )
  }
  if (drift === 'improving') {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-green-500/30 bg-green-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-400">
        <TrendingUp className="h-3 w-3" /> improving {delta != null ? `+${delta.toFixed(1)}pp` : ''}
      </span>
    )
  }
  if (drift === 'stable') {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-white/15 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/60">
        <CheckCircle2 className="h-3 w-3" /> stable
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-400/70">
      <CircleDashed className="h-3 w-3" /> insufficient
    </span>
  )
}

export default function CalibrationPage() {
  const [data, setData] = useState<CalibrationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`${API_URL}/api/v1/calibration/by-transition-type`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then(payload => { if (!cancelled) { setData(payload); setError(null) } })
      .catch(reason => { if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    return [...data.rows].sort((a, b) =>
      Number(b.bullish) - Number(a.bullish)
      || driftOrder[a.drift] - driftOrder[b.drift]
      || b.recent.n_settled - a.recent.n_settled
    )
  }, [data])

  const ft = data?.current_context.follow_through
  const ftIsHostile = ft?.descriptor === 'NOT_PAYING'

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-6xl space-y-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">Calibration</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Evidencia observada, no garantía. Historical muestra el prior; Recent y Same regime indican cuánto se parece esa evidencia al mercado de hoy.
          </p>
        </div>

        {loading && <LoadingSkeleton variant="card" />}
        {error && <p className="text-sm text-destructive">Error: {error}</p>}

        {data && (
          <>
            <Card className={`p-5 ${ftIsHostile ? 'border-red-500/30 bg-red-500/5' : 'border-white/10'}`}>
              <div className="flex items-start gap-3">
                {ftIsHostile
                  ? <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
                  : <Eye className="mt-0.5 h-5 w-5 shrink-0 text-cyan-400" />}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      Contexto actual · {formatRegime(data.current_context.regime)}
                    </p>
                    {ft && (
                      <span className={`text-xs font-bold ${ftIsHostile ? 'text-red-400' : ft.descriptor === 'PAYING' ? 'text-green-400' : 'text-amber-400'}`}>
                        FOLLOW-THROUGH {ft.descriptor}
                      </span>
                    )}
                    {data.current_context.posture && (
                      <span className="text-xs font-semibold text-white/70">POSTURA {data.current_context.posture.state}</span>
                    )}
                  </div>
                  {ft && (
                    <p className="mt-2 text-xs text-white/60">
                      Ventana {ft.window_days}d: {formatPct(ft.delivery_rate)} delivered sobre {ft.resolved} señales settled
                      {ft.baseline_rate != null && ` · baseline ${formatPct(ft.baseline_rate)}`}
                      {` · ${ft.pending} pending`}.
                    </p>
                  )}
                  <p className="mt-2 text-[11px] text-white/40">
                    Una tasa histórica alta no habilita un trade si Recent, Same regime o el follow-through actual no acompañan. As of {data.as_of}.
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="grid grid-cols-2 gap-4 text-center md:grid-cols-4">
                <div>
                  <div className="text-2xl font-bold tabular-nums text-foreground">{data.total_observations}</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">observations</div>
                </div>
                <div>
                  <div className="text-2xl font-bold tabular-nums text-foreground">{data.total_settled}</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">settled</div>
                </div>
                <div>
                  <div className="text-2xl font-bold tabular-nums text-amber-400">{data.total_pending}</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">pending</div>
                </div>
                <div>
                  <div className="text-2xl font-bold tabular-nums text-cyan-400">{data.min_samples_required}</div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">min settled / cohort</div>
                </div>
              </div>
            </Card>

            <Card className="overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1050px] text-sm">
                  <thead className="border-b border-border bg-muted/30">
                    <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                      <th className="px-4 py-2 font-medium">Transition</th>
                      <th className="px-4 py-2 text-right font-medium">All history</th>
                      <th className="px-4 py-2 text-right font-medium">Baseline 180d</th>
                      <th className="px-4 py-2 text-right font-medium">Recent {data.recent_window_days}d</th>
                      <th className="px-4 py-2 text-right font-medium">Same {formatRegime(data.current_context.regime)}</th>
                      <th className="px-4 py-2 font-medium">Drift</th>
                      <th className="px-4 py-2 font-medium">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(row => (
                      <tr key={row.transition_type} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                        <td className="px-4 py-2.5">
                          <div className="font-mono text-xs text-foreground">{row.transition_type}</div>
                          <div className="mt-0.5 text-[9px] uppercase tracking-wide text-white/30">
                            {row.bullish ? 'bullish setup' : 'defensive signal'}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                          <CohortValue cohort={row.historical} minSamples={data.min_samples_required} />
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                          <CohortValue cohort={row.baseline} minSamples={data.min_samples_required} />
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                          <CohortValue cohort={row.recent} minSamples={data.min_samples_required} />
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                          <CohortValue cohort={row.current_regime} minSamples={data.min_samples_required} />
                        </td>
                        <td className="px-4 py-2.5">
                          <DriftBadge drift={row.drift} delta={row.recent_delta_pp} />
                        </td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground">
                          recent n={row.recent.n_settled} · regime n={row.current_regime.n_settled}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <p className="text-center text-[11px] text-muted-foreground">
              Delivered = SUCCESS ÷ (SUCCESS + FAILURE + NEUTRAL). Drift compara Recent 21d contra los 180d anteriores y sólo cambia cuando los intervalos Wilson 95% dejan de superponerse.
            </p>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
