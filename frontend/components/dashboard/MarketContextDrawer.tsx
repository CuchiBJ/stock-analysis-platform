'use client'

import { useState, type ReactNode } from 'react'
import { X, ChevronRight, ChevronDown } from 'lucide-react'
import {
  breadthLevelColor,
  densityLevelColor,
  followThroughColor,
  healthStateColor,
  postureColor,
  DamageStrip,
  type MarketContextData,
} from './MarketContextBar'

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

function postureBg(state: string): string {
  if (state === 'AGRESIVO')  return 'bg-green-500/15 border-green-500/30'
  if (state === 'NORMAL')    return 'bg-white/5 border-white/15'
  if (state === 'SELECTIVO') return 'bg-amber-500/15 border-amber-500/30'
  if (state === 'DEFENSIVO') return 'bg-orange-500/15 border-orange-500/30'
  if (state === 'FUERA')     return 'bg-red-500/15 border-red-500/30'
  return 'bg-white/5 border-white/15'
}

function healthBg(state: string): string {
  if (state === 'ROBUST')     return 'bg-green-500/15 border-green-500/30 text-green-400'
  if (state === 'RECOVERING') return 'bg-sky-500/15 border-sky-500/30 text-sky-400'
  if (state === 'FRAGILE')    return 'bg-amber-500/15 border-amber-500/30 text-amber-400'
  if (state === 'DAMAGED')    return 'bg-red-500/15 border-red-500/30 text-red-400'
  return 'bg-white/5 border-white/15 text-white/50'
}

function followThroughBg(descriptor: string): string {
  if (descriptor === 'PAYING')     return 'bg-green-500/15 border-green-500/30 text-green-400'
  if (descriptor === 'MIXED')      return 'bg-amber-500/15 border-amber-500/30 text-amber-400'
  if (descriptor === 'NOT_PAYING') return 'bg-red-500/15 border-red-500/30 text-red-400'
  return 'bg-white/5 border-white/15 text-white/50'
}

const FT_FAMILY_LABELS: Record<string, string> = {
  pre_reclaim:          'Pullbacks (pre-reclaim)',
  breakout:             'Breakouts',
  reclaim_continuation: 'Reclaims / continuación',
}

function followThroughExplanation(descriptor: string): string {
  if (descriptor === 'PAYING')
    return 'Las señales alcistas recientes están entregando recorrido real (≥1.5 ATR sin invalidarse). El mercado está pagando — el entorno recompensa la exposición.'
  if (descriptor === 'MIXED')
    return 'Pago desparejo: algunas señales entregan, muchas quedan neutras o fallan. Selectividad — solo los setups de mayor calidad justifican riesgo.'
  if (descriptor === 'NOT_PAYING')
    return 'El mercado NO está pagando las señales recientes: los breakouts y rebotes están fallando o quedando neutros. Achicar sin importar cómo se vea la amplitud — es la señal de Qullamaggie: "are you getting paid?"'
  return 'Muestra insuficiente de señales resueltas en la ventana para leer el follow-through.'
}

// One-line read per health state — the WHY behind the badge.
function healthExplanation(state: string, repairMin = 5, repairWindow = 7, severeWindow = 3): string {
  if (state === 'ROBUST')
    return 'Sin deterioro relevante en la ventana: el avance reciente está respaldado por semanas limpias.'
  if (state === 'RECOVERING')
    return `Hubo daño en la ventana, pero el mercado acumuló ≥${repairMin} ruedas limpias de las últimas ${repairWindow} sin recaída severa en las últimas ${severeWindow} — reparación en curso, aún no ROBUST hasta que el daño envejezca.`
  if (state === 'FRAGILE')
    return `Hubo deterioro reciente; el mercado aún no reunió ${repairMin} ruedas limpias de ${repairWindow}, o conserva una recaída severa dentro de las últimas ${severeWindow}. Los pullbacks leves no reinician todo el progreso.`
  if (state === 'DAMAGED')
    return `Deterioro pesado o en curso. Para pasar a RECOVERING se requieren ${repairMin} ruedas limpias de ${repairWindow} y ninguna recaída severa en las últimas ${severeWindow}; un pullback leve consume margen pero no reinicia todo el progreso.`
  return 'Historia insuficiente para clasificar la salud (se requieren ≥10 ruedas clasificables).'
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
  const repairWindow = ctx.health?.repair_window_days ?? 7
  const repairRequired = ctx.health?.repair_required_clean_days ?? 5
  const repairClean = ctx.health?.repair_clean_days ?? ctx.health?.repair_streak ?? 0
  const severeWindow = ctx.health?.severe_lookback_days ?? 3
  const recentSevere = ctx.health?.recent_severe_days ?? 0

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
              participation + leadership + health
            </p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground mt-0.5">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-7">

          {/* ── Section 0: The verdict ── */}
          {ctx.posture && (
            <section className={`px-4 py-3 rounded border ${postureBg(ctx.posture.state)}`}>
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-[10px] uppercase tracking-widest text-white/40">Hoy</span>
                <span className={`text-lg font-black tracking-wide ${postureColor(ctx.posture.state)}`}>
                  {ctx.posture.state}
                </span>
              </div>
              <p className="text-sm text-white/85">{ctx.posture.instruction}</p>
              {ctx.posture.reasons.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {ctx.posture.reasons.map(r => (
                    <li key={r} className="text-[11px] text-white/50">· {r}</li>
                  ))}
                </ul>
              )}
              {ctx.posture.unlock && (
                <p className="text-[11px] text-white/40 mt-2 italic">
                  ↑ {ctx.posture.unlock}
                </p>
              )}
            </section>
          )}

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
            {/* Level (density vs recent norm) — the descriptor above is only a 5d delta */}
            <MetricRow label="Leadership level" value={
              <span className={densityLevelColor(l.metrics.leader_density_level)}>
                {l.metrics.leader_density_level}
                {l.metrics.leader_density_percentile != null && (
                  <span className="text-white/40"> · p{Math.round(l.metrics.leader_density_percentile * 100)}</span>
                )}
              </span>
            } />
            {/* Density delta (universe-normalized) — matches the status bar's headline */}
            <MetricRow label="Leader density Δ 20d"     value={`${l.metrics.leader_density_delta_20d > 0 ? '+' : ''}${l.metrics.leader_density_delta_20d.toFixed(1)}%`} />
            <MetricRow label="Pullback quality avg"     value={l.metrics.leader_pullback_quality_avg.toFixed(1)} />
            <MetricRow label="Climactic count"          value={l.metrics.leader_climactic_count} />
          </section>

          {/* ── Section 3: Health persistence (damage memory) ── */}
          {ctx.health && (
            <section>
              <div className={`flex items-center justify-between px-3 py-2 rounded border mb-3 ${healthBg(ctx.health.state)}`}>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-current/60">Health · memoria {ctx.health.window_days}d</span>
                  <span className="font-bold text-sm tracking-wide">{ctx.health.state}</span>
                </div>
                <span className={`text-xs font-mono ${healthStateColor(ctx.health.state)}`}>
                  {ctx.health.damaged_days}/{ctx.health.window_days} dañados
                </span>
              </div>

              <div className="mb-3">
                <DamageStrip series={ctx.health.series} cellWidth={16} height={14} />
                <p className="text-[10px] text-white/30 mt-1">
                  Últimas {ctx.health.series.length} ruedas — ámbar = pullback leve (NARROWING/THINNING) · rojo = recaída severa (COLLAPSING/EXHAUSTED)
                </p>
              </div>

              <MetricRow label="Días dañados"             value={`${ctx.health.damaged_days} / ${ctx.health.window_days}`} />
              <MetricRow label="Episodios de deterioro"   value={ctx.health.episodes} />
              <MetricRow
                label="Reparación"
                value={`${repairClean}/${repairWindow} limpias · ${recentSevere}/${severeWindow} severas`}
              />
              <MetricRow label="Racha limpia actual"      value={`${ctx.health.repair_streak} rueda${ctx.health.repair_streak === 1 ? '' : 's'}`} />
              <MetricRow
                label="Ruedas desde el último daño"
                value={ctx.health.days_since_last_damage == null ? '—' : ctx.health.days_since_last_damage}
              />

              <p className="text-[11px] text-white/50 mt-3 leading-relaxed">
                {healthExplanation(ctx.health.state, repairRequired, repairWindow, severeWindow)}
              </p>
            </section>
          )}

          {/* ── Section 4: Follow-through (is the market paying?) ── */}
          {ctx.follow_through && (
            <section>
              <div className={`flex items-center justify-between px-3 py-2 rounded border mb-3 ${followThroughBg(ctx.follow_through.descriptor)}`}>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase tracking-widest text-current/60">
                    Follow-through · ventana {ctx.follow_through.window_days}d
                  </span>
                  <span className="font-bold text-sm tracking-wide">{ctx.follow_through.descriptor}</span>
                </div>
                {ctx.follow_through.delivery_rate != null && (
                  <span className="text-xs font-mono">
                    {Math.round(ctx.follow_through.delivery_rate * 100)}% pagando
                    {ctx.follow_through.baseline_rate != null && (
                      <span className="opacity-60"> vs {Math.round(ctx.follow_through.baseline_rate * 100)}% base</span>
                    )}
                  </span>
                )}
              </div>

              <MetricRow label="Señales alcistas en ventana" value={ctx.follow_through.signals} />
              <MetricRow
                label="Resueltas (pagó / falló / neutra)"
                value={`${ctx.follow_through.success} / ${ctx.follow_through.failure} / ${ctx.follow_through.neutral}`}
              />
              {ctx.follow_through.delta_pp != null && (
                <MetricRow
                  label="Delivery vs base histórica"
                  value={
                    <span className={followThroughColor(ctx.follow_through.descriptor)}>
                      {ctx.follow_through.delta_pp > 0 ? '+' : ''}{ctx.follow_through.delta_pp.toFixed(1)}pp
                    </span>
                  }
                />
              )}
              <MetricRow
                label="Frescas (en curso / fallando)"
                value={`${ctx.follow_through.provisional_on_track} / ${ctx.follow_through.provisional_failing}`}
              />
              {Object.entries(ctx.follow_through.per_family).map(([family, f]) => (
                <MetricRow
                  key={family}
                  label={FT_FAMILY_LABELS[family] ?? family}
                  value={
                    f.delivery != null
                      ? `${f.signals} señales · ${Math.round(f.delivery * 100)}% pagando`
                      : `${f.signals} señales · sin resueltas`
                  }
                />
              ))}

              <p className="text-[11px] text-white/50 mt-3 leading-relaxed">
                {followThroughExplanation(ctx.follow_through.descriptor)}
              </p>
            </section>
          )}

          {/* ── Raw metrics toggle ── */}
          <div>
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="flex items-center gap-1.5 text-[11px] text-white/50 hover:text-white/80 transition-colors"
            >
              {showRaw ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Raw metrics (14)
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
                  <MetricRow label="Leader density"                value={`${(l.metrics.leader_density * 100).toFixed(1)}%`} />
                  <MetricRow label="Leader count delta 5d (raw)"   value={l.metrics.leader_count_delta_5d > 0 ? `+${l.metrics.leader_count_delta_5d}` : l.metrics.leader_count_delta_5d} />
                  <MetricRow label="Leader count delta 20d (raw)"  value={l.metrics.leader_count_delta_20d > 0 ? `+${l.metrics.leader_count_delta_20d}` : l.metrics.leader_count_delta_20d} />
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
