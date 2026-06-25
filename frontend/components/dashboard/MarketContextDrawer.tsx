'use client'

import { useState, type ReactNode } from 'react'
import { X, ChevronRight, ChevronDown } from 'lucide-react'
import { breadthLevelColor, type MarketContextData } from './MarketContextBar'

interface Props {
  ctx: MarketContextData
  onClose: () => void
}

function descriptorBg(d: string): string {
  if (d === 'EXPANDING' || d === 'HEALTHY')    return 'bg-green-500/15 border-green-500/30 text-green-400'
  if (d === 'STABLE')                           return 'bg-white/5 border-white/15 text-white/70'
  if (d === 'NARROWING' || d === 'THINNING')   return 'bg-amber-500/15 border-amber-500/30 text-amber-400'
  if (d === 'COLLAPSING' || d === 'EXHAUSTED') return 'bg-red-500/15 border-red-500/30 text-red-400'
  return 'bg-white/5 border-white/15 text-white/50'
}

function MetricRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-white/5 last:border-0">
      <span className="text-xs text-white/50">{label}</span>
      <span className="text-xs font-mono text-white/90">{value}</span>
    </div>
  )
}

function SectionHeader({ title, descriptor, delta, deltaUnit }: {
  title: string
  descriptor: string
  delta: number
  deltaUnit: string
}) {
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded border mb-3 ${descriptorBg(descriptor)}`}>
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-widest text-current/60">{title}</span>
        <span className="font-bold text-sm tracking-wide">{descriptor}</span>
      </div>
      <span className="text-xs font-mono">
        {delta > 0 ? '+' : ''}{delta.toFixed(1)}{deltaUnit} 5d
      </span>
    </div>
  )
}

export default function MarketContextDrawer({ ctx, onClose }: Props) {
  const [showRaw, setShowRaw] = useState(false)
  const p = ctx.participation
  const l = ctx.leadership

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      {/* Backdrop */}
      <div className="flex-1 bg-black/50" />

      {/* Panel */}
      <div
        className="w-full max-w-lg bg-background border-l border-border h-full overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-background border-b border-border px-6 py-4 flex items-start justify-between">
          <div>
            <h2 className="text-base font-bold text-foreground">Market Context</h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Phase 1 — participation + leadership
            </p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground mt-0.5">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-7">

          {/* ── Section 1: Participation ── */}
          <section>
            <SectionHeader
              title="Participation"
              descriptor={p.descriptor}
              delta={p.delta_5d}
              deltaUnit="pp"
            />
            <MetricRow label="Breadth above EMA21"  value={<span className={breadthLevelColor(p.metrics.breadth_above_ema21 * 100)}>{(p.metrics.breadth_above_ema21 * 100).toFixed(1)}%</span>} />
            <MetricRow label="Breadth momentum 5d"  value={`${(p.metrics.breadth_momentum_5d * 100).toFixed(2)}pp`} />
            <MetricRow label="Highs / lows ratio"   value={p.metrics.highs_lows_ratio.toFixed(2)} />
          </section>

          {/* ── Section 2: Leadership ── */}
          <section>
            <SectionHeader
              title="Leadership Quality"
              descriptor={l.descriptor}
              delta={l.delta_5d}
              deltaUnit="%"
            />
            <MetricRow label="Leader count"             value={l.metrics.leader_count} />
            <MetricRow label="Leader count delta 20d"   value={l.metrics.leader_count_delta_20d > 0 ? `+${l.metrics.leader_count_delta_20d}` : l.metrics.leader_count_delta_20d} />
            <MetricRow label="Pullback quality avg"     value={l.metrics.leader_pullback_quality_avg.toFixed(1)} />
            <MetricRow label="Climactic count"          value={l.metrics.leader_climactic_count} />
          </section>

          {/* ── Raw metrics toggle ── */}
          <div>
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="flex items-center gap-1.5 text-[11px] text-white/50 hover:text-white/80 transition-colors"
            >
              {showRaw ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Raw metrics (12)
            </button>

            {showRaw && (
              <div className="mt-4 space-y-5">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-white/25 mb-2">Participation raw</p>
                  <MetricRow label="Breadth above EMA50"       value={`${(p.metrics.breadth_above_ema50 * 100).toFixed(1)}%`} />
                  <MetricRow label="Breadth above EMA200"      value={`${(p.metrics.breadth_above_ema200 * 100).toFixed(1)}%`} />
                  <MetricRow label="Breadth momentum 20d"      value={`${(p.metrics.breadth_momentum_20d * 100).toFixed(2)}pp`} />
                  <MetricRow label="Near highs count"          value={p.metrics.near_highs_count} />
                  <MetricRow label="Near lows count"           value={p.metrics.near_lows_count} />
                  <MetricRow label="Participation persistence" value={p.metrics.participation_persistence.toFixed(4)} />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-white/25 mb-2">Leadership raw</p>
                  <MetricRow label="Leader count delta 5d"         value={l.metrics.leader_count_delta_5d > 0 ? `+${l.metrics.leader_count_delta_5d}` : l.metrics.leader_count_delta_5d} />
                  <MetricRow label="Weekly tightness avg"          value={l.metrics.leader_tightness_avg.toFixed(3)} />
                  <MetricRow label="Vol contraction avg"           value={l.metrics.leader_vol_contraction_avg.toFixed(3)} />
                  <MetricRow label="RS persistence 10d"            value={`${(l.metrics.leader_rs_persistence_10d * 100).toFixed(1)}%`} />
                  <MetricRow label="Extension count (>3 ATR)"      value={l.metrics.leader_extension_count} />
                  <MetricRow label="Leadership turnover 5d"        value={l.metrics.leadership_turnover_5d} />
                </div>
              </div>
            )}
          </div>

          {/* ── Footer ── */}
          <footer className="pt-2 border-t border-white/8 space-y-1">
            <p className="text-[10px] text-white/30">
              As of <span className="text-white/50">{ctx.as_of}</span>
              {' · '}universe <span className="text-white/50">{ctx.universe_size}</span> stocks
            </p>
            <p className="text-[10px] text-white/25">
              Phase 2–4 pending: {ctx.engines_pending.join(' · ')}
            </p>
          </footer>

        </div>
      </div>
    </div>
  )
}
