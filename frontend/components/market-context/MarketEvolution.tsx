'use client'

import { useMemo, useState } from 'react'
import {
  evolutionSegments,
  joinEvolutionSeverity,
  normalizeEvolution,
  type EvolutionSession,
} from '@/lib/market-context-evolution'
import type { MarketOverview } from '@/lib/market-context'

const chartLeft = 30
const chartRight = 970
const chartTop = 10
const chartBottom = 84

function xPosition(index: number, count: number) {
  return count < 1 ? (chartLeft + chartRight) / 2 : chartLeft + (chartRight - chartLeft) * (index + 0.5) / count
}

function severityLabel(session: EvolutionSession) {
  if (!session.severity) return 'Sin datos'
  return session.severity === 'clean' ? 'Sin daño clasificado' : session.severity === 'mild' ? 'Daño leve' : 'Daño severo'
}

function coverageLabel(covered: number, total: number) {
  return `${covered}/${total}`
}

function EvolutionChart({
  title,
  unit,
  points,
  selectedIndex,
  valueFor,
  maximum,
  formatValue,
}: {
  title: string
  unit: string
  points: EvolutionSession[]
  selectedIndex: number
  valueFor: 'breadthRatio' | 'leaderCount'
  maximum: number
  formatValue: (value: number) => string
}) {
  const values = points.map(point => point[valueFor])
  const segments = evolutionSegments(points, valueFor)
  const yFor = (value: number) => chartBottom - (value / maximum) * (chartBottom - chartTop)
  const selected = points[selectedIndex]
  const selectedValue = selected?.[valueFor]
  const markerX = xPosition(selectedIndex, points.length)
  const pathFor = (segment: Array<{ date: string; value: number }>) => segment.map((point, segmentIndex) => {
    const index = points.findIndex(candidate => candidate.date === point.date)
    return `${segmentIndex === 0 ? 'M' : 'L'} ${xPosition(index, points.length)} ${yFor(point.value)}`
  }).join(' ')

  return <figure className="min-w-0" aria-label={`${title}, ${unit}; escala de 0 a ${formatValue(maximum)}`}>
    <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs">
      <span className="font-medium">{title}</span>
      <span className="text-muted-foreground">{unit} · {coverageLabel(values.filter(value => value != null).length, points.length)} · 0–{formatValue(maximum)}</span>
    </figcaption>
    <svg className="mt-1 block h-24 w-full overflow-visible" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" aria-label={`${title}: ${values.filter(value => value != null).length} de ${points.length} sesiones disponibles; escala de 0 a ${formatValue(maximum)} ${unit}`}>
      <title>{`${title} · ${unit}`}</title>
      <line x1={chartLeft} x2={chartRight} y1={chartBottom} y2={chartBottom} stroke="currentColor" strokeOpacity=".25" vectorEffect="non-scaling-stroke" />
      <line x1={markerX} x2={markerX} y1={chartTop} y2={chartBottom} stroke="currentColor" strokeOpacity=".65" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      {segments.map((segment, index) => <path key={index} d={pathFor(segment)} fill="none" stroke="currentColor" strokeWidth="1.7" vectorEffect="non-scaling-stroke" />)}
      {points.map((point, index) => {
        const value = point[valueFor]
        if (value == null) return null
        return <circle key={point.date} cx={xPosition(index, points.length)} cy={yFor(value)} r={index === selectedIndex ? 3.2 : 2.4} fill="hsl(var(--background))" stroke="currentColor" strokeWidth={index === selectedIndex ? 2 : 1.5} vectorEffect="non-scaling-stroke"><title>{`${point.date}: ${formatValue(value)} ${unit}`}</title></circle>
      })}
    </svg>
    <div className="flex justify-between font-mono text-[10px] text-muted-foreground"><span>{points[0]?.date}</span><span>{selectedValue == null ? 'Sin datos' : formatValue(selectedValue)}</span><span>{points.at(-1)?.date}</span></div>
  </figure>
}

function DamageStrip({ points, selectedIndex }: { points: EvolutionSession[]; selectedIndex: number }) {
  const classes = {
    clean: 'border-slate-500 bg-slate-500/70',
    mild: 'border-amber-400 bg-amber-400/75',
    severe: 'border-red-500 bg-red-500/80',
    unknown: 'border-dashed border-muted-foreground/60 bg-transparent',
  }
  return <div className="mt-1 grid h-3 gap-px px-[3%]" style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }} role="img" aria-label={`Daño por sesión: ${points.map(point => `${point.date}, ${severityLabel(point)}`).join('; ')}`}>
    {points.map((point, index) => <span key={point.date} className={`border ${classes[point.severity ?? 'unknown']} ${index === selectedIndex ? 'ring-1 ring-foreground' : ''}`} title={`${point.date}: ${severityLabel(point)}`} />)}
  </div>
}

export default function MarketEvolution({ data }: { data: MarketOverview }) {
  const { evolution, context } = data
  const points = useMemo(() => normalizeEvolution(evolution, context.as_of), [evolution, context.as_of])
  const sessions = useMemo(() => joinEvolutionSeverity(points, context.health?.series ?? [], context.as_of), [points, context.health, context.as_of])
  const [selection, setSelection] = useState<string | null>(null)
  const latestDate = sessions.at(-1)?.date ?? null
  const selectedDate = sessions.some(session => session.date === selection)
    ? selection
    : latestDate

  if (sessions.length === 0) return <section className="rounded border border-border bg-card p-4" aria-labelledby="evolution-title">
    <h3 id="evolution-title" className="text-sm font-medium">Evolución reciente · hasta 20 ruedas</h3>
    <p className="mt-3 text-sm text-muted-foreground">Evolución no disponible</p>
  </section>

  const selectedIndex = Math.max(0, sessions.findIndex(session => session.date === (selectedDate ?? latestDate)))
  const selected = sessions[selectedIndex]
  const severityCount = sessions.filter(session => session.severity != null).length
  const leaderMaximum = Math.max(1, ...sessions.map(session => session.leaderCount ?? 0))
  const breadthMaximum = 1
  const percent = (value: number) => `${(value * 100).toFixed(1)}%`
  const count = (value: number) => `${value}`
  const outdated = sessions.at(-1)!.date < context.as_of

  return <section className="rounded border border-border bg-card p-4" aria-labelledby="evolution-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 id="evolution-title" className="text-sm font-medium">Evolución reciente · hasta 20 ruedas</h3>
        <p className="mt-1 text-xs text-muted-foreground">{sessions.length} sesiones · {sessions[0].date}—{sessions.at(-1)!.date}{sessions.length < 20 ? ` · ${sessions.length} sesiones disponibles` : ''}{outdated ? ` · última sesión anterior al contexto (${context.as_of})` : ''}</p>
      </div>
      <div className="flex flex-col items-start gap-1 text-xs"><label htmlFor="market-evolution-session" className="text-muted-foreground">Inspeccionar sesión</label><span className="text-[10px] text-muted-foreground">Cambia sólo la inspección de esta serie.</span>
        <select id="market-evolution-session" value={selected.date} onChange={event => setSelection(event.target.value)} className="rounded border border-border bg-background px-2 py-1 font-mono focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">
          {sessions.map(session => <option key={session.date} value={session.date}>{session.date}</option>)}
        </select>
      </div>
    </div>
    <div className="mt-3 grid gap-x-5 gap-y-2 border-y border-border/70 py-3 text-xs sm:grid-cols-3">
      <p>Sobre EMA21 <strong className="ml-1 font-mono">{selected.breadthRatio == null ? 'Sin datos' : percent(selected.breadthRatio)}</strong></p>
      <p>Líderes <strong className="ml-1 font-mono">{selected.leaderCount == null ? 'Sin datos' : count(selected.leaderCount)}</strong></p>
      <p>Daño <strong className="ml-1">{severityLabel(selected)}</strong></p>
    </div>
    <div className="mt-3 grid gap-3">
      <EvolutionChart title="Amplitud" unit="Sobre EMA21 (%)" points={sessions} selectedIndex={selectedIndex} valueFor="breadthRatio" maximum={breadthMaximum} formatValue={percent} />
      <EvolutionChart title="Liderazgo" unit="Cantidad de líderes" points={sessions} selectedIndex={selectedIndex} valueFor="leaderCount" maximum={leaderMaximum} formatValue={count} />
    </div>
    <div className="mt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs"><span className="font-medium">Daño · {coverageLabel(severityCount, sessions.length)} clasificados</span><span className="text-muted-foreground">{sessions[0].date} <span className="mx-1">→</span> {sessions.at(-1)!.date}</span></div>
      <DamageStrip points={sessions} selectedIndex={selectedIndex} />
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
        <li><span className="mr-1 inline-block h-2 w-2 border border-slate-500 bg-slate-500/70" />Sin daño clasificado</li>
        <li><span className="mr-1 inline-block h-2 w-2 border border-amber-400 bg-amber-400/75" />Daño leve</li>
        <li><span className="mr-1 inline-block h-2 w-2 border border-red-500 bg-red-500/80" />Daño severo</li>
        <li><span className="mr-1 inline-block h-2 w-2 border border-dashed border-muted-foreground/60" />Sin datos</li>
      </ul>
    </div>
    <p className="mt-3 text-[10px] text-muted-foreground">Amplitud usa escala 0–100%; líderes usa cantidad de acciones (0–{leaderMaximum}). Escalas independientes; cobertura visible por serie. Las sesiones sin observación no se interpolan.</p>
  </section>
}
