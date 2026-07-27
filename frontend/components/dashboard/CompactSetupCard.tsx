'use client'

import Link from 'next/link'
import { Flame } from 'lucide-react'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'

interface GroupStrength {
  group: string | null
  badge: 'leader' | 'neutral' | 'weak'
  multiplier?: number
}

interface ScoreBreakdownComponent {
  name: string
  kind: string
  contribution: number
  max_contribution: number
}

interface ScoreBreakdown {
  components: ScoreBreakdownComponent[]
}

// Splits the priority score into its drivers by `kind` so the operator sees how
// much of the ranking is the stock's own quality vs. market regime (not
// controllable) vs. freshness. Segment widths are fractions of 1.0, so the
// empty remainder = points the setup did NOT earn (e.g. regime drag in a weak tape).
function ScoreKindBar({ components }: { components: ScoreBreakdownComponent[] }) {
  const sumKind = (k: string) =>
    components.filter(c => c.kind === k).reduce((a, c) => a + (c.contribution || 0), 0)
  const quality = sumKind('symbol_controllable')
  const regime  = sumKind('market_wide')
  const fresh   = sumKind('time_dependent')
  const total   = quality + regime + fresh
  if (total <= 0) return null

  const pct = (x: number) => Math.round(x * 100)
  const w   = (x: number) => `${(x * 100).toFixed(1)}%`

  return (
    <div title="Composición del score de prioridad — el vacío es lo no ganado (ej. drag de régimen)">
      <div className="flex h-1 rounded-full overflow-hidden bg-white/10">
        <div className="bg-emerald-400/80" style={{ width: w(quality) }} title={`Calidad propia ${pct(quality)}% · controlable`} />
        <div className="bg-amber-400/80"   style={{ width: w(regime) }}  title={`Régimen ${pct(regime)}% · mercado, no controlable`} />
        <div className="bg-sky-400/70"     style={{ width: w(fresh) }}   title={`Freshness ${pct(fresh)}% · tiempo en estado`} />
      </div>
      <div className="flex justify-between text-[9px] text-white/40 mt-0.5 leading-none">
        <span>tú {pct(quality)}%</span>
        <span className="text-amber-400/70">mercado {pct(regime)}%</span>
        <span>fresh {pct(fresh)}%</span>
      </div>
    </div>
  )
}

interface CompactSetupCardProps {
  symbol: string
  state: string
  transition: string
  transitionStrength: number
  narrative: string
  confidence: number
  freshness: string
  daysInState: number
  keyMetrics: {
    ema21: string
    rs: number
    volume: string
    base?: string
  }
  sector?: string
  isPriority?: boolean
  observationPriority?: number
  isPreReclaim?: boolean
  sparklineData?: number[]
  priceLabel?: string | null
  contextWarnings?: string[]
  groupStrength?: GroupStrength | null
  scoreBreakdown?: ScoreBreakdown | null
}

const FRESHNESS: Record<string, { label: string; cls: string }> = {
  fresh:        { label: 'fresh', cls: 'text-green-400  bg-green-400/10  border-green-400/20'  },
  aging:        { label: 'aging', cls: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20' },
  'late-stage': { label: 'late',  cls: 'text-orange-400 bg-orange-400/10 border-orange-400/20' },
  stale:        { label: 'stale', cls: 'text-red-400    bg-red-400/10    border-red-400/20'    },
  extended:     { label: 'ext',   cls: 'text-red-500    bg-red-500/10    border-red-500/20'    },
}

export default function CompactSetupCard({
  symbol,
  state,
  narrative,
  confidence,
  freshness,
  keyMetrics,
  isPriority = false,
  isPreReclaim = false,
  priceLabel,
  contextWarnings,
  groupStrength,
  scoreBreakdown,
}: CompactSetupCardProps) {
  // Priority score (0–1) rendered as a 0–100 quality score — más accionable
  // que la probabilidad de continuación, que era casi idéntica entre acciones
  // con el mismo setup.
  const scorePts = confidence != null ? Math.round(confidence * 100) : null

  const accentBorder =
    scorePts !== null && scorePts >= 70 ? 'border-l-green-500' :
    scorePts !== null && scorePts >= 50 ? 'border-l-yellow-500' :
                                          'border-l-white/10'

  const scoreColor =
    scorePts === null ? 'text-white/30' :
    scorePts >= 70    ? 'text-green-400' :
    scorePts >= 50    ? 'text-yellow-400' :
                        'text-orange-400'

  const freshInfo = FRESHNESS[freshness] ?? FRESHNESS.fresh

  return (
    <Link
      href={`/stock/${symbol}`}
      className={`
        w-full flex flex-col gap-2.5 p-3 rounded-lg
        bg-white/5 border border-white/8 border-l-2 ${accentBorder}
        ${isPriority ? 'ring-1 ring-orange-400/30 bg-orange-400/5' : ''}
        cursor-pointer hover:bg-white/8 transition-colors
      `}>

      {/* Row 1: Symbol + badges + continuation prob */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="font-bold text-sm text-white tracking-wide">{symbol}</span>
          {isPriority && <Flame className="w-3 h-3 text-orange-400 shrink-0" />}
          {isPreReclaim && (
            <span className="text-[9px] px-1 py-0.5 rounded border border-cyan-400/30 bg-cyan-400/10 text-cyan-400 uppercase tracking-wide shrink-0">
              watch
            </span>
          )}
          <span className={`text-[9px] px-1 py-0.5 rounded border ${freshInfo.cls} uppercase tracking-wide shrink-0`}>
            {freshInfo.label}
          </span>
        </div>
        {scorePts !== null && (
          <div className="flex items-center gap-1">
            {contextWarnings?.includes('leadership_exhausted') && (
              <span className="text-[9px] px-1 py-0.5 rounded border border-amber-400/30 bg-amber-400/10 text-amber-400 leading-none">
                exhausted
              </span>
            )}
            <span
              className={`text-base font-bold tabular-nums ${scoreColor}`}
              title="Score de prioridad del setup (0–100)"
            >
              {scorePts}
              <span className="text-[10px] font-normal text-white/30 ml-0.5">/100</span>
            </span>
          </div>
        )}
      </div>

      {/* Row 2: State label + price context */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-white/40 uppercase tracking-widest">{state}</span>
        {priceLabel && (
          <span className="text-[10px] font-mono text-white/60 text-right">{priceLabel}</span>
        )}
      </div>

      {/* Row 2b: Score composition by kind — quality vs regime vs freshness */}
      {scoreBreakdown?.components && <ScoreKindBar components={scoreBreakdown.components} />}

      {/* Row 3: Narrative */}
      <p className="text-xs text-white/75 leading-snug">{narrative}</p>

      {/* Row 4: Metrics — Dist, RS, Vol */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        <div className="text-[10px]">
          <span className="text-white/40">Dist  </span>
          <span className="text-white/70">{keyMetrics.ema21}</span>
        </div>
        <div className="text-[10px]">
          <span className="text-white/40">RS  </span>
          <span className="text-white/70">{keyMetrics.rs || '—'}</span>
        </div>
        <div className="text-[10px]">
          <span className="text-white/40">Vol  </span>
          <span className="text-white/70">{keyMetrics.volume}</span>
        </div>
      </div>

      {/* Row 5: Group strength badge (only leader/weak — neutral renders null) */}
      {groupStrength && (
        <GroupStrengthBadge group={groupStrength.group} badge={groupStrength.badge} />
      )}
    </Link>
  )
}
