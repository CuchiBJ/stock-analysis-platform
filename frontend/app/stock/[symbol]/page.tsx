'use client'

import React, { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { API_URL } from '@/lib/utils'
import DashboardLayout from '@/components/layout/DashboardLayout'
import Card from '@/components/base/Card'
import LoadingSkeleton from '@/components/base/LoadingSkeleton'
import GroupStrengthBadge from '@/components/shared/GroupStrengthBadge'
import { CheckCircle2, XCircle, ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react'

interface Criterion {
  name: string
  actual: any
  threshold: any
  passes: boolean
  kind: string
}

interface Cutoff {
  kind: string
  n: number
  ranked_by: string
  note: string
}

interface SubComponent {
  name: string
  points: number
  max_points: number
  raw_value: number | null
  verdict: string
}

interface ScoreComponent {
  name: string
  value: number
  max_value: number
  contribution: number
  max_contribution: number
  to_improve: number
  kind: 'symbol_controllable' | 'time_dependent' | 'market_wide' | 'group_rotation'
  note: string
  sub_components?: SubComponent[]
}

interface AssessmentGap {
  name: string
  severity: 'blocker' | 'high' | 'medium' | 'low'
  what_to_do: string
}

interface Assessment {
  verdict: 'elite' | 'strong' | 'mid' | 'weak' | 'disqualified'
  headline: string
  strengths: string[]
  gaps: AssessmentGap[]
}

interface MultiplierInfo {
  value: number
  max_value: number
  kind: string
  badge?: string
  group?: string | null
}

interface ScoreBreakdown {
  components: ScoreComponent[]
  base_score: number
  after_regime_adjust: number
  ctx_multiplier: MultiplierInfo
  group_multiplier: MultiplierInfo
  final_priority_unclamped: number
  final_priority: number
  clamped: boolean
}

interface ListCheck {
  key: string
  name: string
  passes: boolean
  criteria: Criterion[]
  cutoff?: Cutoff | null
  appears_in_endpoint?: boolean
  rank_in_endpoint?: number | null
  total_in_endpoint?: number
  score_breakdown?: ScoreBreakdown | null
}

interface TransitionEntry {
  transition_type: string
  date_detected: string | null
  outcome_status: string
}

interface DiagnosticResponse {
  header: {
    symbol: string
    name: string | null
    sector: string | null
    industry: string | null
    market_group: string | null
    current_price: number | null
    has_metrics: boolean
    metrics_date: string | null
    is_latest: boolean
  }
  note?: string
  lists: ListCheck[]
  transition_history: TransitionEntry[]
  market_context_applied: {
    participation: string
    leadership: string
    score_multiplier: number
    suppress_lenses: string[]
    surface_warnings: string[]
  } | null
  group_strength: {
    group: string | null
    badge: 'leader' | 'neutral' | 'weak'
    multiplier: number
  } | null
  minervini_status: Record<string, any> | null
  assessment?: Assessment | null
}

// ─── Human-readable labels ───────────────────────────────────────────────────
const MINERVINI_LABELS: Record<string, string> = {
  perf_1y_gt_30:              'Performance anual > 30%',
  price_above_ema200:         'Precio sobre EMA200',
  price_above_ema50:          'Precio sobre EMA50',
  sma50_gt_sma150:            'SMA50 > SMA150',
  sma150_gt_sma200_x_105:     'SMA150 > SMA200 × 1.05',
  range_52w_gte_60pct:        'Rango 52 semanas ≥ 60%',
  price_above_low_gte_70pct:  'Precio sobre mínimo 52w ≥ 70%',
  adr_gte_3pct:               'ADR ≥ 3%',
}

const SCORE_COMPONENT_LABELS: Record<string, string> = {
  pullback_quality:  'Calidad del pullback',
  freshness:         'Freshness — días en estado',
  regime_alignment:  'Alineación con régimen',
  leader_quality:    'Calidad de líder',
}

function componentLabel(name: string): string {
  return SCORE_COMPONENT_LABELS[name] ?? name
}

function minerviniLabel(key: string): string {
  return MINERVINI_LABELS[key] ?? key
}

function formatValue(v: any): string {
  if (v === null || v === undefined) return 'null'
  if (typeof v === 'number') {
    if (Math.abs(v) >= 10_000) return Math.round(v).toLocaleString()
    if (Number.isInteger(v)) return String(v)
    return v.toFixed(2)
  }
  if (Array.isArray(v)) return `[${v.map(formatValue).join(', ')}]`
  return String(v)
}

function ListRow({ lst }: { lst: ListCheck }) {
  // Three states:
  //   "in_list":     passes criteria AND appears in endpoint (or no cutoff)   → green
  //   "below_cutoff": passes criteria but ranks below cutoff                  → amber
  //   "fails":       at least one criterion fails                              → red
  const hasCutoff = !!lst.cutoff
  const state = !lst.passes
    ? 'fails'
    : hasCutoff && lst.appears_in_endpoint === false
      ? 'below_cutoff'
      : 'in_list'

  const [open, setOpen] = useState(state !== 'in_list')

  const Icon = state === 'in_list' ? CheckCircle2 : state === 'below_cutoff' ? AlertTriangle : XCircle
  const palette =
    state === 'in_list' ? 'text-green-400' :
    state === 'below_cutoff' ? 'text-amber-400' :
    'text-red-400'
  const failedCount = lst.criteria.filter(c => !c.passes).length
  const totalInEndpoint = lst.total_in_endpoint ?? null

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
        <Icon className={`w-4 h-4 ${palette}`} />
        <span className="text-sm text-foreground flex-1">{lst.name}</span>
        {state === 'in_list' && lst.rank_in_endpoint != null && totalInEndpoint != null && (
          <span className="text-[10px] uppercase tracking-wider text-green-400">
            rank {lst.rank_in_endpoint}/{totalInEndpoint}
          </span>
        )}
        {state === 'below_cutoff' && (
          <span className="text-[10px] uppercase tracking-wider text-amber-400">
            below top {lst.cutoff?.n}
          </span>
        )}
        {state === 'fails' && (
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {failedCount} criteri{failedCount === 1 ? 'on' : 'a'} fail
          </span>
        )}
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 bg-muted/10">
          {lst.cutoff && (
            <div className={`text-[11px] mb-2 px-2 py-1.5 rounded border ${
              state === 'below_cutoff'
                ? 'border-amber-500/30 bg-amber-500/5 text-amber-300'
                : 'border-white/10 bg-white/5 text-muted-foreground'
            }`}>
              <span className="font-semibold">Cutoff:</span> top {lst.cutoff.n} by {lst.cutoff.ranked_by}.
              {state === 'below_cutoff' && ' Passes filter but ranks below cutoff — does not appear in the list.'}
            </div>
          )}
          <table className="w-full text-xs">
            <tbody>
              {lst.criteria.map((c, i) => (
                <tr key={i} className="border-b border-border/30 last:border-0">
                  <td className="py-1.5 pr-3 align-top">
                    {c.passes
                      ? <CheckCircle2 className="w-3.5 h-3.5 text-green-400/70" />
                      : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                  </td>
                  <td className="py-1.5 pr-3 text-foreground/80">{c.name}</td>
                  <td className="py-1.5 pr-3 font-mono tabular-nums text-right text-muted-foreground">
                    {formatValue(c.actual)}
                  </td>
                  <td className="py-1.5 font-mono tabular-nums text-muted-foreground/60">
                    vs {formatValue(c.threshold)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {lst.score_breakdown && <ScoreBreakdownTable bd={lst.score_breakdown} listPassed={lst.passes} />}
        </div>
      )}
    </div>
  )
}

function AssessmentCard({ a }: { a: Assessment }) {
  const verdictStyle: Record<Assessment['verdict'], { label: string; pill: string; bg: string }> = {
    elite:         { label: 'Élite',         pill: 'bg-green-500/20 text-green-300 border-green-500/40',  bg: 'border-green-500/30 bg-green-500/5'   },
    strong:        { label: 'Fuerte',        pill: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',     bg: 'border-cyan-500/30 bg-cyan-500/5'     },
    mid:           { label: 'Mid-tier',      pill: 'bg-amber-500/20 text-amber-300 border-amber-500/40', bg: 'border-amber-500/30 bg-amber-500/5'   },
    weak:          { label: 'Débil',         pill: 'bg-orange-500/20 text-orange-300 border-orange-500/40', bg: 'border-orange-500/30 bg-orange-500/5' },
    disqualified:  { label: 'Descalificado', pill: 'bg-red-500/20 text-red-300 border-red-500/40',       bg: 'border-red-500/30 bg-red-500/5'       },
  }
  const v = verdictStyle[a.verdict]
  const severityStyle: Record<AssessmentGap['severity'], string> = {
    blocker: 'border-red-500/40 bg-red-500/5 text-red-300',
    high:    'border-orange-500/40 bg-orange-500/5 text-orange-300',
    medium:  'border-amber-500/40 bg-amber-500/5 text-amber-300',
    low:     'border-white/15 bg-white/5 text-white/70',
  }

  return (
    <Card className={`p-5 border ${v.bg}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`text-[10px] uppercase tracking-widest px-2 py-1 rounded border ${v.pill}`}>
          {v.label}
        </span>
        <span className="text-xs uppercase tracking-widest text-muted-foreground">Quality Assessment</span>
      </div>
      <p className="text-sm text-foreground mb-3">{a.headline}</p>

      {a.strengths.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Fortalezas</p>
          <ul className="space-y-1">
            {a.strengths.map((s, i) => (
              <li key={i} className="text-xs text-green-400/90 flex gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {a.gaps.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
            {a.verdict === 'elite' || a.verdict === 'strong' ? 'Áreas marginales' : 'Qué le falta para ser top'}
          </p>
          <ul className="space-y-2">
            {a.gaps.map((g, i) => (
              <li key={i} className={`text-xs px-2.5 py-2 rounded border ${severityStyle[g.severity]}`}>
                <div className="font-semibold flex items-center gap-2">
                  <XCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{g.name}</span>
                  <span className="text-[9px] uppercase tracking-wider opacity-60 ml-auto">{g.severity}</span>
                </div>
                <p className="mt-1 ml-5 opacity-90 leading-snug">{g.what_to_do}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}

function kindLabel(kind: ScoreComponent['kind']): { tag: string; cls: string } {
  switch (kind) {
    case 'symbol_controllable': return { tag: 'actionable',  cls: 'text-green-400'  }
    case 'time_dependent':      return { tag: 'time-decay',  cls: 'text-amber-400'  }
    case 'market_wide':         return { tag: 'market-wide', cls: 'text-white/40'   }
    case 'group_rotation':      return { tag: 'group',       cls: 'text-cyan-400'   }
    default:                    return { tag: kind,          cls: 'text-white/40'   }
  }
}

function SubComponentsTable({ subs }: { subs: SubComponent[] }) {
  return (
    <div className="my-2 ml-4 pl-3 border-l-2 border-amber-500/30">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
        Sub-componentes de pullback quality
      </p>
      <table className="w-full text-[11px]">
        <tbody>
          {subs.map((s, i) => {
            const filled = s.max_points > 0 ? s.points / s.max_points : 0
            const cls = filled >= 0.85 ? 'text-green-400' : filled >= 0.5 ? 'text-amber-300' : 'text-red-400'
            return (
              <tr key={i} className="border-b border-border/30 last:border-0">
                <td className="py-1 pr-2 text-foreground/80">{s.name}</td>
                <td className="py-1 pr-2 text-right font-mono tabular-nums">
                  <span className={cls}>{s.points.toFixed(0)}</span>
                  <span className="text-white/30 ml-0.5">/{s.max_points}</span>
                </td>
                <td className="py-1 text-foreground/60 leading-snug">{s.verdict}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ScoreBreakdownTable({ bd, listPassed }: { bd: ScoreBreakdown; listPassed: boolean }) {
  const components = bd.components
  const ctxAtMax = bd.ctx_multiplier.value >= bd.ctx_multiplier.max_value - 0.001
  const grpAtMax = bd.group_multiplier.value >= bd.group_multiplier.max_value - 0.001

  return (
    <div className="mt-4 pt-3 border-t border-white/10">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
        Score breakdown {!listPassed && <span className="text-amber-400">· hypothetical — list criteria fail</span>}
      </p>

      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
            <th className="text-left  py-1 pr-3">Component</th>
            <th className="text-right py-1 pr-3">Contribution</th>
            <th className="text-right py-1 pr-3">Max</th>
            <th className="text-right py-1 pr-3">To improve</th>
            <th className="text-left  py-1">Kind</th>
          </tr>
        </thead>
        <tbody>
          {components.map((c, i) => {
            const k = kindLabel(c.kind)
            const filledPct = Math.min(100, Math.round((c.contribution / c.max_contribution) * 100))
            return (
              <React.Fragment key={i}>
                <tr className="border-b border-border/30 last:border-0">
                  <td className="py-1.5 pr-3 text-foreground/80">{componentLabel(c.name)}</td>
                  <td className="py-1.5 pr-3 text-right font-mono tabular-nums">
                    <span className="text-foreground">{c.contribution.toFixed(3)}</span>
                    <span className="text-white/30 text-[10px] ml-1">({filledPct}%)</span>
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono tabular-nums text-muted-foreground/60">
                    {c.max_contribution.toFixed(3)}
                  </td>
                  <td className="py-1.5 pr-3 text-right font-mono tabular-nums">
                    {c.to_improve > 0.001
                      ? <span className="text-amber-300">+{c.to_improve.toFixed(3)}</span>
                      : <span className="text-green-400">at max</span>}
                  </td>
                  <td className="py-1.5">
                    <span className={`text-[10px] uppercase tracking-wider ${k.cls}`}>{k.tag}</span>
                  </td>
                </tr>
                {c.sub_components && c.sub_components.length > 0 && (
                  <tr>
                    <td colSpan={5} className="px-0 py-0">
                      <SubComponentsTable subs={c.sub_components} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
          <tr className="border-b border-white/10 bg-white/3">
            <td className="py-1.5 pr-3 font-mono text-foreground/60 italic">base score</td>
            <td className="py-1.5 pr-3 text-right font-mono tabular-nums text-foreground">
              {bd.base_score.toFixed(3)}
            </td>
            <td className="py-1.5 pr-3 text-right font-mono tabular-nums text-muted-foreground/60">1.000</td>
            <td className="py-1.5 pr-3 text-right font-mono tabular-nums">
              {bd.base_score >= 0.999
                ? <span className="text-green-400">at max</span>
                : <span className="text-amber-300">+{(1.0 - bd.base_score).toFixed(3)}</span>}
            </td>
            <td />
          </tr>
        </tbody>
      </table>

      <div className="mt-3 grid grid-cols-2 gap-x-4 text-xs">
        <div className="flex justify-between">
          <span className="text-foreground/80">× context multiplier</span>
          <span className="font-mono tabular-nums">
            <span className="text-foreground">{bd.ctx_multiplier.value.toFixed(2)}</span>
            <span className="text-white/30 ml-1">/ {bd.ctx_multiplier.max_value.toFixed(2)}</span>
            {ctxAtMax && <span className="text-green-400 ml-1">✓</span>}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground/80">
            × group multiplier
            {bd.group_multiplier.group && (
              <span className="text-white/40 text-[10px] ml-1">({bd.group_multiplier.group})</span>
            )}
          </span>
          <span className="font-mono tabular-nums">
            <span className="text-foreground">{bd.group_multiplier.value.toFixed(2)}</span>
            <span className="text-white/30 ml-1">/ {bd.group_multiplier.max_value.toFixed(2)}</span>
            {grpAtMax && <span className="text-green-400 ml-1">✓</span>}
          </span>
        </div>
      </div>

      <div className="mt-3 pt-2 border-t border-white/10 flex justify-between items-center text-xs">
        <span className="text-foreground/80 uppercase tracking-wider text-[10px]">
          final priority
        </span>
        <div className="text-right">
          <span className="font-mono tabular-nums text-base text-foreground">
            {bd.final_priority.toFixed(3)}
          </span>
          {bd.clamped && (
            <span className="text-[10px] text-amber-400 ml-2">
              clamped from {bd.final_priority_unclamped.toFixed(3)}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function outcomeBadge(status: string) {
  const colors: Record<string, string> = {
    SUCCESS: 'border-green-500/40 bg-green-500/10 text-green-400',
    FAILURE: 'border-red-500/40 bg-red-500/10 text-red-400',
    NEUTRAL: 'border-amber-500/40 bg-amber-500/10 text-amber-400',
    PENDING: 'border-white/15 bg-white/5 text-white/50',
    INSUFFICIENT_DATA: 'border-white/15 bg-white/5 text-white/40',
  }
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border uppercase tracking-wide ${colors[status] ?? colors.PENDING}`}>
      {status}
    </span>
  )
}

export default function SymbolPage() {
  const params = useParams()
  const symbol = String(params?.symbol ?? '').toUpperCase()
  const [data, setData] = useState<DiagnosticResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_URL}/api/v1/stocks/${symbol}/diagnostic`)
      .then(async r => {
        if (r.status === 404) throw new Error(`Symbol ${symbol} not found`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => { if (!cancelled) { setData(d); setError(null) } })
      .catch(e => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [symbol])

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-4">
        {loading && <LoadingSkeleton variant="card" />}

        {error && (
          <Card className="p-6 border-red-500/30 bg-red-500/5">
            <p className="text-sm text-red-300">{error}</p>
          </Card>
        )}

        {data && (
          <>
            {/* Header */}
            <Card className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-foreground">{data.header.symbol}</h1>
                    {data.group_strength && (
                      <GroupStrengthBadge group={data.group_strength.group} badge={data.group_strength.badge} />
                    )}
                  </div>
                  {data.header.name && (
                    <p className="text-sm text-muted-foreground mt-1">{data.header.name}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {data.header.sector} · {data.header.industry}
                  </p>
                </div>
                <div className="text-right">
                  {data.header.current_price != null && (
                    <div className="text-2xl font-mono tabular-nums text-foreground">
                      ${data.header.current_price.toFixed(2)}
                    </div>
                  )}
                  <p className="text-[10px] text-muted-foreground mt-1">
                    metrics @ <span className="font-mono">{data.header.metrics_date ?? 'none'}</span>
                    {!data.header.is_latest && data.header.metrics_date && (
                      <span className="ml-1 text-amber-400">· not latest snapshot</span>
                    )}
                  </p>
                </div>
              </div>
            </Card>

            {data.note && (
              <Card className="p-4 border-amber-500/30 bg-amber-500/5">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-amber-300">{data.note}</p>
                </div>
              </Card>
            )}

            {/* Quality Assessment — top-level "why is this where it is + what's missing" */}
            {data.assessment && <AssessmentCard a={data.assessment} />}

            {/* Status across lists */}
            {data.lists.length > 0 && (
              <Card className="p-0 overflow-hidden">
                <div className="px-4 py-3 border-b border-border/50">
                  <h2 className="text-xs uppercase tracking-widest text-muted-foreground">Status across lists</h2>
                </div>
                {data.lists.map(lst => <ListRow key={lst.key} lst={lst} />)}
              </Card>
            )}

            {/* Market context applied */}
            {data.market_context_applied && (
              <Card className="p-4">
                <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Market context applied</h2>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Participation</div>
                    <div className="font-mono text-foreground mt-1">{data.market_context_applied.participation}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Leadership</div>
                    <div className="font-mono text-foreground mt-1">{data.market_context_applied.leadership}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Score multiplier</div>
                    <div className="font-mono text-foreground mt-1">×{data.market_context_applied.score_multiplier.toFixed(2)}</div>
                  </div>
                </div>
                {data.market_context_applied.suppress_lenses.length > 0 && (
                  <p className="text-[11px] text-amber-300 mt-3">
                    Suppresses lenses: {data.market_context_applied.suppress_lenses.join(', ')}
                  </p>
                )}
              </Card>
            )}

            {/* Transition history */}
            {data.transition_history.length > 0 && (
              <Card className="p-4">
                <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3">
                  Transition history · last 30 days
                </h2>
                <div className="space-y-1.5">
                  {data.transition_history.map((t, i) => (
                    <div key={i} className="flex items-center gap-3 text-xs">
                      <span className="font-mono text-muted-foreground tabular-nums w-24 shrink-0">{t.date_detected}</span>
                      <span className="font-mono text-foreground flex-1">{t.transition_type}</span>
                      {outcomeBadge(t.outcome_status)}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Minervini breakdown (optional, useful when quality_leader fails) */}
            {data.minervini_status && (
              <Card className="p-4">
                <h2 className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Minervini SEPA breakdown</h2>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(data.minervini_status).map(([key, val]: [string, any]) => (
                    <div key={key} className={`px-2 py-1.5 rounded border ${val.passes ? 'border-green-500/30 bg-green-500/5 text-green-400' : 'border-red-500/30 bg-red-500/5 text-red-400'}`}>
                      <div className="flex items-center gap-1.5">
                        {val.passes ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        <span>{minerviniLabel(key)}</span>
                      </div>
                      {val.value != null && val.threshold != null && (
                        <div className="text-[10px] opacity-75 mt-0.5 ml-4">
                          {typeof val.value === 'number' ? val.value.toFixed(1) : val.value}
                          {' / '}
                          {typeof val.threshold === 'number' ? val.threshold.toFixed(1) : val.threshold}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
