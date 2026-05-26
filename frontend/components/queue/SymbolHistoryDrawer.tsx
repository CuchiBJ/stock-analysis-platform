'use client'

import { useEffect, useState } from 'react'
import { API_URL } from '@/lib/utils'
import { X } from 'lucide-react'

interface Observation {
  date_detected: string
  transition_type: string
  outcome_status: string
  distance_to_ema21_atr_at_detection: number | null
  pct_5d: number | null
  pct_20d: number | null
  regime_at_detection: string | null
}

interface TrackRecordEntry {
  success_rate: number | null
  sample_size: number
}

interface History {
  symbol: string
  current_regime: string
  observations: Observation[]
  track_record: Record<string, TrackRecordEntry>
}

interface Props {
  symbol: string
  onClose: () => void
}

function outcomeColor(s: string) {
  if (s === 'SUCCESS') return 'bg-green-500/20 text-green-400 border-green-500/30'
  if (s === 'FAILURE') return 'bg-red-500/20 text-red-400 border-red-500/30'
  if (s === 'NEUTRAL') return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
  if (s === 'PENDING') return 'bg-muted/40 text-muted-foreground border-border'
  return 'bg-muted/40 text-muted-foreground border-border'
}

export default function SymbolHistoryDrawer({ symbol, onClose }: Props) {
  const [data, setData] = useState<History | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/queue/symbol/${symbol}/history?days=30`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d => { if (!cancelled) setData(d) })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [symbol])

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="flex-1 bg-black/50" />
      <div
        className="w-full max-w-md bg-background border-l border-border h-full overflow-y-auto p-6"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-foreground">{symbol}</h2>
            {data && (
              <p className="text-xs text-muted-foreground mt-1">
                Régimen actual: <span className="text-foreground">{data.current_regime}</span>
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Cargando…</p>}
        {error && <p className="text-sm text-destructive">Error: {error}</p>}

        {data && (
          <>
            <section className="mb-6">
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                Arco de transitions (últimos 30 días)
              </h3>
              {data.observations.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin observations en este rango.</p>
              ) : (
                <div className="space-y-2">
                  {data.observations.map((o, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <div className="font-mono text-muted-foreground w-20">{o.date_detected}</div>
                      <div className="flex-1 text-foreground">
                        {o.transition_type.replace(/_/g, ' ').toUpperCase()}
                      </div>
                      <div className={`px-2 py-0.5 rounded border text-[10px] ${outcomeColor(o.outcome_status)}`}>
                        {o.outcome_status}
                      </div>
                      {o.pct_5d != null && (
                        <div className={`font-mono w-14 text-right ${o.pct_5d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {o.pct_5d >= 0 ? '+' : ''}{o.pct_5d.toFixed(1)}%
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                Track record (régimen actual)
              </h3>
              {Object.keys(data.track_record).length === 0 ? (
                <p className="text-sm text-muted-foreground">Aún sin sample suficiente.</p>
              ) : (
                <div className="space-y-1">
                  {Object.entries(data.track_record).map(([key, tr]) => (
                    <div key={key} className="flex items-center justify-between text-xs py-1 border-b border-border/40 last:border-0">
                      <span className="text-foreground">{key.replace(/_/g, ' ')}</span>
                      <span className="font-mono text-muted-foreground">
                        {tr.success_rate != null ? `${(tr.success_rate * 100).toFixed(0)}%` : '—'}
                        {' '}
                        <span className="opacity-60">(n={tr.sample_size})</span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}
