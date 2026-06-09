'use client'

import { useEffect } from 'react'
import { X, AlertOctagon, AlertTriangle, Activity } from 'lucide-react'
import type { HealthSnapshot, PipelineHeartbeat } from '@/types/health'
import {
  dotClass,
  formatRelativeTime,
  isCycleStaleByAge,
} from './pipelineHealthUtils'

interface Props {
  open: boolean
  onClose: () => void
  snapshot: HealthSnapshot
}

function heartbeatColor(hb: PipelineHeartbeat): 'red' | 'amber' | 'green' {
  if (hb.status === 'failed') return 'red'
  if (hb.status === 'partial' || isCycleStaleByAge(hb)) return 'amber'
  return 'green'
}

function coverageBarColor(pct: number): string {
  if (pct < 80) return 'bg-red-500'
  if (pct < 95) return 'bg-amber-500'
  return 'bg-emerald-500'
}

export default function PipelineHealthDrawer({ open, onClose, snapshot }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const { coverage, market_state, pipeline_heartbeats, recent_errors, recent_errors_24h } = snapshot
  const pct = Math.round(coverage.pct)
  const barColor = coverageBarColor(coverage.pct)

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden
      />
      {/* Sheet */}
      <aside
        role="dialog"
        aria-label="Pipeline health detail"
        className="absolute right-0 top-0 h-full w-[420px] max-w-full bg-card border-l border-border shadow-2xl overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Pipeline health</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Coverage */}
        <section className="px-4 py-4 border-b border-border">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs uppercase tracking-wider text-muted-foreground">Universe coverage</h3>
            <span className="text-xs font-mono text-foreground">
              {coverage.actual}/{coverage.expected} ({pct}%)
            </span>
          </div>
          <div className="w-full h-2 bg-white/10 rounded overflow-hidden">
            <div
              className={`h-full ${barColor} transition-all`}
              style={{ width: `${Math.min(100, Math.max(0, coverage.pct))}%` }}
            />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Quality universe symbols refreshed since today's market open.
          </p>
        </section>

        {/* Cycles */}
        <section className="px-4 py-4 border-b border-border">
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Cycles</h3>
          {pipeline_heartbeats.length === 0 ? (
            <p className="text-xs text-muted-foreground">No heartbeats recorded yet.</p>
          ) : (
            <ul className="space-y-3">
              {pipeline_heartbeats.map((hb) => {
                const color = heartbeatColor(hb)
                const showProgress =
                  hb.symbols_processed != null && hb.symbols_expected != null && hb.symbols_expected > 0
                const progressPct = showProgress
                  ? Math.min(100, Math.round((hb.symbols_processed! / hb.symbols_expected!) * 100))
                  : 0
                const staleByAge = isCycleStaleByAge(hb)
                return (
                  <li key={hb.cycle_name} className="text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`h-2 w-2 rounded-full ${dotClass(color)} shrink-0`} />
                        <span className="font-mono truncate">{hb.cycle_name}</span>
                        {staleByAge && (
                          <span className="text-[10px] uppercase text-amber-400">stale</span>
                        )}
                      </div>
                      <div className="text-muted-foreground shrink-0">
                        {formatRelativeTime(hb.last_run_at)}
                        <span className="ml-2 opacity-60">{hb.last_duration_seconds.toFixed(1)}s</span>
                      </div>
                    </div>
                    {showProgress && (
                      <div className="mt-1.5 ml-4">
                        <div className="w-full h-1 bg-white/10 rounded overflow-hidden">
                          <div
                            className={`h-full ${color === 'red' ? 'bg-red-500' : color === 'amber' ? 'bg-amber-500' : 'bg-emerald-500'}`}
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                        <div className="mt-0.5 text-[10px] text-muted-foreground">
                          {hb.symbols_processed}/{hb.symbols_expected}
                        </div>
                      </div>
                    )}
                    {hb.last_error_message && (
                      <div className="mt-1 ml-4 text-[10px] text-red-400 font-mono truncate" title={hb.last_error_message}>
                        {hb.last_error_message}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        {/* Market state */}
        <section className="px-4 py-4 border-b border-border">
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Market state</h3>
          <div className="text-xs space-y-1">
            <div>
              <span className="text-muted-foreground">Phase:</span>{' '}
              <span className="font-mono">{market_state.session_phase}</span>
            </div>
            {market_state.minutes_since_open != null && (
              <div>
                <span className="text-muted-foreground">Minutes since open:</span>{' '}
                <span className="font-mono">{market_state.minutes_since_open}</span>
              </div>
            )}
          </div>
          {market_state.is_warmup && (
            <div className="mt-3 p-2 rounded border border-amber-500/30 bg-amber-500/10 text-amber-300 text-[11px]">
              Durante warmup, métricas dependientes de tick (regime, RS) son ruidosas.
              Mejor confiar en setups con state ≥ 1 día.
            </div>
          )}
        </section>

        {/* Recent errors */}
        {recent_errors_24h > 0 && (
          <section className="px-4 py-4">
            <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
              <AlertOctagon className="w-3.5 h-3.5 text-red-400" />
              Recent errors (24h)
            </h3>
            <ul className="space-y-2">
              {recent_errors.map((e, idx) => (
                <li key={idx} className="text-[11px] border-l-2 border-red-500/40 pl-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-foreground">{e.task_name}</span>
                    <span className="text-muted-foreground">{formatRelativeTime(e.occurred_at)}</span>
                  </div>
                  <div className="text-red-400 font-mono">{e.exception_type}</div>
                  <div className="text-muted-foreground truncate" title={e.exception_message}>
                    {e.exception_message}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        {snapshot.is_stale && (
          <section className="px-4 py-3 border-t border-border bg-amber-500/5">
            <div className="flex items-start gap-2 text-[11px] text-amber-300">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <div>
                Metrics {snapshot.metrics_lag_days}d behind prices ·
                metrics @ <span className="font-mono">{snapshot.stock_metrics_latest}</span> ·
                prices @ <span className="font-mono">{snapshot.stock_price_latest}</span>
              </div>
            </div>
          </section>
        )}
      </aside>
    </div>
  )
}
