'use client'

import { useEffect, useState, useCallback } from 'react'
import { API_URL } from '@/lib/utils'
import MarketContextDrawer from './MarketContextDrawer'

// Mirror of backend Phase 1 rules — kept in sync with context_decision_filter.py
function getAffectedLenses(participation: string, leadership: string): string[] {
  const p = participation.toUpperCase()
  const l = leadership.toUpperCase()
  if (p === 'UNKNOWN' || l === 'UNKNOWN') return []
  if (p === 'COLLAPSING') return ['U&R', 'Emerging Leaders']
  const adverse = ['THINNING', 'COLLAPSING', 'EXHAUSTED']
  if (p === 'NARROWING' && adverse.includes(l)) return ['Emerging Leaders']
  return []
}

// ─── Type definitions (mirrors spec API contract) ─────────────────────────────

interface HistoryPoint {
  date: string
  value: number
}

interface ParticipationData {
  descriptor: string
  delta_5d: number
  delta_sample_size_20d: number
  history?: HistoryPoint[]
  metrics: {
    breadth_above_ema21:       number
    breadth_above_ema50:       number
    breadth_above_ema200:      number
    breadth_momentum_5d:       number
    breadth_momentum_20d:      number
    near_highs_count:          number
    near_lows_count:           number
    highs_lows_ratio:          number
    participation_persistence: number
  }
}

interface LeadershipData {
  descriptor: string
  delta_5d: number
  history?: HistoryPoint[]
  metrics: {
    leader_count:                number
    leader_count_delta_5d:       number
    leader_count_delta_20d:      number
    leader_pullback_quality_avg: number
    leader_tightness_avg:        number
    leader_vol_contraction_avg:  number
    leader_rs_persistence_10d:   number
    leader_extension_count:      number
    leader_climactic_count:      number
    leadership_turnover_5d:      number
  }
}

interface IndexData {
  symbol: string
  price: number
  change_pct: number | null
  trend: string
  above_ema50: boolean
  above_ema200: boolean
}

export interface MarketContextData {
  as_of: string
  universe_size: number
  participation: ParticipationData
  leadership: LeadershipData
  engines_pending: string[]
  index?: IndexData | null
}

// ─── Descriptor styling ───────────────────────────────────────────────────────

function descriptorStyle(d: string): string {
  if (d === 'EXPANDING' || d === 'HEALTHY')   return 'text-green-400'
  if (d === 'STABLE')                          return 'text-white/70'
  if (d === 'NARROWING' || d === 'THINNING')  return 'text-amber-400'
  if (d === 'COLLAPSING' || d === 'EXHAUSTED') return 'text-red-400'
  return 'text-white/50'  // unknown descriptor — neutral (Risk 7)
}

function deltaArrow(delta: number): string {
  if (delta > 1) return '↑'
  if (delta < -1) return '↓'
  return '→'
}

function deltaColor(delta: number): string {
  if (delta > 1) return 'text-green-400'
  if (delta < -1) return 'text-red-400'
  return 'text-white/50'
}

// Breadth LEVEL color — distinguishes stable-healthy from stable-weak, which the
// descriptor (a 5d delta) collapses into the same "STABLE" word. Cuts mirror the
// 2x2 read: >55% = mayoría participando, <35% = lavado/apático.
export function breadthLevelColor(pct: number): string {
  if (pct >= 55) return 'text-green-400'
  if (pct >= 35) return 'text-amber-400'
  return 'text-red-400'
}

function trendColor(trend: string): string {
  if (trend === 'alcista') return 'text-green-400'
  if (trend === 'bajista') return 'text-red-400'
  return 'text-amber-400'  // lateral
}

function changeColor(pct: number | null): string {
  if (pct == null) return 'text-white/50'
  if (pct > 0) return 'text-green-400'
  if (pct < 0) return 'text-red-400'
  return 'text-white/50'
}

// Tiny inline SVG sparkline — shows the recent trajectory of an engine so its
// evolution is visible at a glance (vs only today's value + 5d delta).
function MiniSparkline({
  data,
  width = 52,
  height = 14,
}: { data: HistoryPoint[]; width?: number; height?: number }) {
  if (!data || data.length < 2) return null
  const vals = data.map(d => d.value)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const pad = 1.5
  const stepX = (width - pad * 2) / (vals.length - 1)
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2)
  const pts = vals.map((v, i) => `${(pad + i * stepX).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  // Color by RECENT direction (last ~3 trading days), not the whole window — the
  // 5d delta already conveys the medium-term trend; the sparkline's job is to
  // surface the recent inflection (e.g. collapsing 5d but ticking back up now).
  const ref = vals[Math.max(0, vals.length - 3)]
  const last = vals[vals.length - 1]
  const stroke = last > ref ? '#4ade80' : last < ref ? '#f87171' : '#9ca3af'
  const lastX = pad + (vals.length - 1) * stepX
  const lastY = y(vals[vals.length - 1])
  const dir = last > ref ? 'subiendo' : last < ref ? 'bajando' : 'estable'
  return (
    <svg width={width} height={height} className="shrink-0 overflow-visible">
      <title>Últimos {vals.length} días — recientemente {dir}</title>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.25} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r={1.6} fill={stroke} />
    </svg>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function MarketContextBar() {
  const [ctx, setCtx] = useState<MarketContextData | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [suppressionTooltip, setSuppressionTooltip] = useState(false)

  const fetchContext = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/market-context/current`)
      if (r.ok) setCtx(await r.json())
    } catch {}
  }, [])

  useEffect(() => {
    fetchContext()
    const interval = setInterval(fetchContext, 60_000)
    return () => clearInterval(interval)
  }, [fetchContext])

  if (!ctx) {
    return (
      <div className="flex items-center px-4 py-2.5 rounded-lg border border-white/10 bg-white/5">
        <span className="text-xs text-white/30">Loading market context…</span>
      </div>
    )
  }

  const p = ctx.participation
  const l = ctx.leadership
  const breadthPct = Math.round(p.metrics.breadth_above_ema21 * 100)
  const affectedLenses = getAffectedLenses(p.descriptor, l.descriptor)

  return (
    <>
      <button
        className="w-full text-left px-4 py-2.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/8 transition-colors cursor-pointer"
        onClick={() => setDrawerOpen(true)}
      >
        {/* Line 1: engine descriptors + deltas */}
        <div className="flex items-center gap-4 text-xs">
          {ctx.index && (
            <>
              <div className="flex items-center gap-1.5 shrink-0" title={`Tendencia: ${ctx.index.trend}`}>
                <span className={`font-bold tracking-wide ${trendColor(ctx.index.trend)}`}>
                  {ctx.index.symbol}
                </span>
                <span className="font-mono tabular-nums text-white/80">
                  {ctx.index.price.toFixed(2)}
                </span>
                {ctx.index.change_pct != null && (
                  <span className={`text-[10px] font-semibold ${changeColor(ctx.index.change_pct)}`}>
                    {ctx.index.change_pct > 0 ? '+' : ''}{ctx.index.change_pct.toFixed(2)}%
                  </span>
                )}
              </div>
              <span className="text-white/20 shrink-0">·</span>
            </>
          )}

          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-white/40 uppercase tracking-widest text-[10px]">Participation</span>
            <span className={`font-bold tracking-wide ${descriptorStyle(p.descriptor)}`}>
              {p.descriptor}
            </span>
            <span className={`text-[10px] font-semibold ${deltaColor(p.delta_5d)}`}>
              {deltaArrow(p.delta_5d)}{Math.abs(p.delta_5d).toFixed(1)}pp
            </span>
            <span
              className={`text-[10px] font-bold tabular-nums ${breadthLevelColor(breadthPct)}`}
              title="Breadth: % del universo sobre EMA21 — verde sano (≥55%) / ámbar mixto (35–55%) / rojo débil (<35%). El descriptor mide el delta 5d; este número, el nivel."
            >
              {breadthPct}%
            </span>
            {p.history && <MiniSparkline data={p.history} />}
          </div>

          <span className="text-white/20 shrink-0">·</span>

          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-white/40 uppercase tracking-widest text-[10px]">Leadership</span>
            <span className={`font-bold tracking-wide ${descriptorStyle(l.descriptor)}`}>
              {l.descriptor}
            </span>
            <span className={`text-[10px] font-semibold ${deltaColor(l.delta_5d)}`}>
              {deltaArrow(l.delta_5d)}{Math.abs(l.delta_5d).toFixed(1)}%
            </span>
            {l.history && <MiniSparkline data={l.history} />}
          </div>

          <div className="ml-auto flex items-center gap-2">
            {affectedLenses.length > 0 && (
              <div className="relative">
                <button
                  className="text-[10px] text-amber-400/80 hover:text-amber-400 flex items-center gap-1 transition-colors"
                  onClick={e => { e.stopPropagation(); setSuppressionTooltip(v => !v) }}
                  title={`Suprime: ${affectedLenses.join(', ')}`}
                >
                  · suprime {affectedLenses.length} lens{affectedLenses.length > 1 ? 'es' : ''}
                </button>
                {suppressionTooltip && (
                  <div className="absolute right-0 top-5 z-50 bg-zinc-900 border border-amber-400/20 rounded px-3 py-2 text-[10px] text-white/70 whitespace-nowrap shadow-lg">
                    {affectedLenses.map(lens => (
                      <div key={lens} className="py-0.5">· {lens}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
            <span className="text-[10px] text-white/20">{ctx.as_of}</span>
          </div>
        </div>

        {/* Line 2: key raw metrics */}
        <div className="flex items-center gap-4 mt-1 text-[10px] text-white/40">
          <span>breadth <span className={breadthLevelColor(breadthPct)}>{breadthPct}%</span></span>
          <span>momentum <span className={deltaColor(p.delta_5d)}>{p.delta_5d > 0 ? '+' : ''}{p.delta_5d.toFixed(1)}pp</span></span>
          <span>leaders <span className="text-white/70">{l.metrics.leader_count}</span>
            {l.metrics.leader_count_delta_20d !== 0 && (
              <span className={deltaColor(l.metrics.leader_count_delta_20d)}>
                {' '}({l.metrics.leader_count_delta_20d > 0 ? '+' : ''}{l.metrics.leader_count_delta_20d}/20d)
              </span>
            )}
          </span>
          <span className="text-white/20">click for full tablero</span>
        </div>
      </button>

      {drawerOpen && (
        <MarketContextDrawer
          ctx={ctx}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </>
  )
}
