'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { X } from 'lucide-react'
import { API_URL } from '@/lib/utils'

interface ConstituentStock {
  symbol: string
  name: string | null
  current_price: number | null
  score: number        // puntaje (pullback quality)
  structure: number    // estructura 0-100
  rs: number
  dist_ema21_atr: number | null
  adr_percent: number | null
  perf_1w: number | null
  composite: number
}

interface GroupConstituents {
  group: string
  as_of: string | null
  count: number
  stocks: ConstituentStock[]
}

function scoreColor(v: number): string {
  if (v >= 70) return 'text-green-400'
  if (v >= 55) return 'text-amber-400'
  return 'text-red-400'
}

export default function SectorConstituentsDrawer({ group, onClose }: { group: string | null; onClose: () => void }) {
  const [data, setData] = useState<GroupConstituents | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!group) return
    let active = true
    setLoading(true); setError(false); setData(null)
    fetch(`${API_URL}/api/v1/sectors/group-stocks?group=${encodeURIComponent(group)}`)
      .then(r => { if (!r.ok) throw new Error('failed'); return r.json() })
      .then(d => { if (active) setData(d) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [group])

  // Close on Escape
  useEffect(() => {
    if (!group) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [group, onClose])

  if (!group) return null

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="flex-1 bg-black/50" />
      <div
        className="w-full max-w-lg bg-background border-l border-border h-full overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-start justify-between">
          <div>
            <h2 className="text-base font-bold text-foreground">{group}</h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {data ? `${data.count} acciones · ordenadas por puntaje + estructura` : 'Acciones del sector'}
            </p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground mt-0.5">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-4 py-4">
          {loading && <p className="text-sm text-muted-foreground px-2">Cargando…</p>}
          {error && <p className="text-sm text-red-400 px-2">No se pudieron cargar las acciones.</p>}
          {data && data.stocks.length === 0 && (
            <p className="text-sm text-muted-foreground px-2">Sin acciones que cumplan el filtro de calidad.</p>
          )}

          {data && data.stocks.length > 0 && (
            <>
              {/* column headers */}
              <div className="grid grid-cols-[1.4rem_1fr_auto_auto_auto] gap-2 px-2 pb-1.5 text-[10px] uppercase tracking-wide text-white/35">
                <span>#</span>
                <span>Símbolo</span>
                <span className="text-right">Puntaje</span>
                <span className="text-right">Estruct.</span>
                <span className="text-right">RS</span>
              </div>

              <div className="space-y-1">
                {data.stocks.map((s, i) => (
                  <Link
                    key={s.symbol}
                    href={`/stock/${s.symbol}`}
                    className="grid grid-cols-[1.4rem_1fr_auto_auto_auto] gap-2 items-center px-2 py-2 rounded hover:bg-white/5 transition-colors"
                  >
                    <span className="text-[11px] text-white/30 tabular-nums">{i + 1}</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-foreground">{s.symbol}</span>
                        {s.current_price != null && (
                          <span className="text-[10px] font-mono text-foreground/60">${s.current_price.toFixed(2)}</span>
                        )}
                        {s.perf_1w != null && (
                          <span className={`text-[10px] font-mono ${s.perf_1w >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {s.perf_1w >= 0 ? '+' : ''}{s.perf_1w.toFixed(1)}% 1s
                          </span>
                        )}
                      </div>
                      {s.name && <div className="text-[10px] text-muted-foreground truncate">{s.name}</div>}
                    </div>
                    <span className={`text-right text-sm font-semibold tabular-nums ${scoreColor(s.score)}`}>{s.score.toFixed(0)}</span>
                    <span className={`text-right text-sm tabular-nums ${scoreColor(s.structure)}`}>{s.structure.toFixed(0)}</span>
                    <span className="text-right text-sm tabular-nums text-foreground/80">{s.rs.toFixed(0)}</span>
                  </Link>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
