'use client'

import { useEffect, useState } from 'react'
import { API_URL } from '@/lib/utils'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import { Eye, CircleDashed, CheckCircle2, AlertTriangle } from 'lucide-react'

interface CalibrationRow {
  transition_type: string
  n_resolved: number
  n_pending: number
  success_count: number
  failure_count: number
  success_rate: number | null
  status: 'empirical' | 'insufficient' | 'no_data'
}

interface CalibrationResponse {
  min_samples_required: number
  total_observations: number
  total_resolved: number
  total_pending: number
  eta_first_data: string | null
  rows: CalibrationRow[]
}

function StatusBadge({ status }: { status: CalibrationRow['status'] }) {
  if (status === 'empirical') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-green-500/30 bg-green-500/10 text-green-400 uppercase tracking-wide">
        <CheckCircle2 className="w-3 h-3" /> empirical
      </span>
    )
  }
  if (status === 'insufficient') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-400 uppercase tracking-wide">
        <AlertTriangle className="w-3 h-3" /> insufficient
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-white/15 bg-white/5 text-white/40 uppercase tracking-wide">
      <CircleDashed className="w-3 h-3" /> no data
    </span>
  )
}

function rowNote(row: CalibrationRow, minSamples: number): string {
  if (row.status === 'empirical') {
    return `${row.success_count} success · ${row.failure_count} failure`
  }
  if (row.status === 'insufficient') {
    const need = minSamples - row.n_resolved
    return `Need ${need} more · ${row.success_count}/${row.failure_count} so far`
  }
  return row.n_pending > 0 ? `${row.n_pending} pending` : 'no observations yet'
}

export default function CalibrationPage() {
  const [data, setData] = useState<CalibrationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/calibration/by-transition-type`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d => { if (!cancelled) { setData(d); setError(null) } })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const empiricalCount = data?.rows.filter(r => r.status === 'empirical').length ?? 0

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">Calibration</h1>
          <p className="text-xs text-muted-foreground mt-1">
            Tasa de éxito empírica observada por transition type. Los outcomes se resuelven 10 días post-detección.
          </p>
        </div>

        {loading && <LoadingSkeleton variant="card" />}
        {error && <p className="text-sm text-destructive">Error: {error}</p>}

        {data && (
          <>
            {data.total_resolved === 0 ? (
              <Card className="p-5 border-amber-400/30 bg-amber-400/5">
                <div className="flex items-start gap-3">
                  <Eye className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-amber-300">
                      Sistema observando — ningún outcome resuelto aún
                    </p>
                    <p className="text-xs text-white/60 mt-1">
                      {data.total_observations} observation{data.total_observations === 1 ? '' : 's'} registrada{data.total_observations === 1 ? '' : 's'}
                      {data.total_pending > 0 && ` · ${data.total_pending} pending`}
                      {data.eta_first_data && ` · primera data esperada ${data.eta_first_data}`}
                    </p>
                    <p className="text-[11px] text-white/40 mt-2">
                      Threshold: {data.min_samples_required}+ observations resueltas (SUCCESS o FAILURE) por transition_type para mostrar success rate empírica.
                    </p>
                  </div>
                </div>
              </Card>
            ) : (
              <Card className="p-4">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-2xl font-bold text-foreground tabular-nums">{data.total_observations}</div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">total obs</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-foreground tabular-nums">{data.total_resolved}</div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">resolved</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-400 tabular-nums">{empiricalCount}</div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">empirical types</div>
                  </div>
                </div>
              </Card>
            )}

            <Card className="p-0 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 border-b border-border">
                  <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Transition</th>
                    <th className="px-4 py-2 font-medium text-right">N</th>
                    <th className="px-4 py-2 font-medium text-right">Success rate</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map(row => (
                    <tr key={row.transition_type} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                      <td className="px-4 py-2.5 font-mono text-xs text-foreground">
                        {row.transition_type}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">
                        {row.n_resolved}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums">
                        {row.success_rate !== null
                          ? <span className="text-foreground">{(row.success_rate * 100).toFixed(1)}%</span>
                          : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">
                        {rowNote(row, data.min_samples_required)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <p className="text-[11px] text-muted-foreground text-center">
              Phase 1 in-sample calibration. Out-of-sample (predicted vs actual) requiere persistir <span className="font-mono">predicted_probability_at_detection</span> — defer.
            </p>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
