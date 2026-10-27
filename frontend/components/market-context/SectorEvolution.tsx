import { useId, useState } from 'react'
import type { NormalizedSectorEvolution, SectorEvolutionPoint, TopTwoConcentration } from '@/lib/market-context-sector-evolution'

function percent(rate: number | null): string {
  return rate == null ? 'Sin cobertura' : `${(rate * 100).toFixed(1)}%`
}

function dateEvidence(point: SectorEvolutionPoint): string {
  return `${point.date}: ${point.high_count} ${point.high_count === 1 ? 'máximo' : 'máximos'}, ${point.low_count} ${point.low_count === 1 ? 'mínimo' : 'mínimos'}; ${point.eligible_symbols} elegibles, ${point.excluded_symbols} excluidas`
}

function latestRateText(point: SectorEvolutionPoint | null, side: 'high' | 'low', date: string, includeDate = true): string {
  if (!point) return `Sin observación (${date})`
  if (point.eligible_symbols === 0) return `Sin cobertura (${date})`
  const count = side === 'high' ? point.high_count : point.low_count
  const ratio = side === 'high' ? point.high_rate : point.low_rate
  return `${count}/${point.eligible_symbols} (${percent(ratio)})${includeDate ? ` · ${date}` : ''}`
}

function deltaClass(side: 'high' | 'low', delta: number): string {
  const deteriorates = side === 'high' ? delta < 0 : delta > 0
  if (delta === 0) return 'text-muted-foreground'
  return deteriorates ? 'text-red-400' : 'text-green-400'
}

function lineSegments(points: Array<SectorEvolutionPoint | null>, key: 'high_rate' | 'low_rate') {
  const segments: Array<Array<{ x: number; y: number; date: string; rate: number }>> = []
  let segment: Array<{ x: number; y: number; date: string; rate: number }> = []
  const width = 120
  const height = 24
  points.forEach((point, index) => {
    const value = point?.[key]
    if (point == null || value == null) {
      if (segment.length) segments.push(segment)
      segment = []
      return
    }
    segment.push({
      x: points.length <= 1 ? width / 2 : index * width / (points.length - 1),
      y: 2 + (1 - value) * height,
      date: point.date,
      rate: value,
    })
  })
  if (segment.length) segments.push(segment)
  return segments
}

function Sparkline({ points, side, sector }: { points: Array<SectorEvolutionPoint | null>; side: 'high_rate' | 'low_rate'; sector: string }) {
  const segments = lineSegments(points, side)
  const label = side === 'high_rate' ? 'máximos' : 'mínimos'
  const color = side === 'high_rate' ? 'text-green-400' : 'text-red-400'
  const available = points.filter(point => point?.[side] != null).length
  const description = points.map(point => point ? `${point.date}: ${percent(point[side])} ${label}` : 'Sesión sin observación').join('; ')
  return <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-2" role="img" aria-label={`${sector}, tasa de ${label} sobre escala fija 0–100%. ${description}`}>
    <span className={`text-[10px] ${color}`}>{label} · 0–100%</span>
    {available === 0 ? <span className="text-[10px] text-muted-foreground">Sin cobertura</span> : <svg viewBox="0 0 120 28" className="h-6 w-full overflow-visible" aria-hidden="true" preserveAspectRatio="none">
      <path d="M0 2H120 M0 26H120" className="stroke-border" strokeWidth="0.5" fill="none" />
      {segments.map((segment, segmentIndex) => segment.length > 1 && <path key={`line-${segmentIndex}`} d={segment.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x},${point.y}`).join(' ')} className={`fill-none stroke-current ${color}`} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />)}
      {segments.flatMap((segment, segmentIndex) => segment.map((point, pointIndex) => <path key={`${segmentIndex}-${pointIndex}`} d={`M${point.x},${point.y}h0.01`} strokeLinecap="round" strokeWidth="3" vectorEffect="non-scaling-stroke" className={`stroke-current ${color}`}><title>{`${point.date}: ${(point.rate * 100).toFixed(1)}% ${label}`}</title></path>))}
    </svg>}
  </div>
}

function concentrationText(item: TopTwoConcentration): string {
  if (item.state === 'no-coverage') return 'Sin cobertura; concentración no disponible'
  if (item.state === 'no-events') return 'Sin eventos; concentración no disponible'
  return `${item.event_count}/${item.total_events} eventos (${(item.percent * 100).toFixed(1)}%)`
}

function Concentration({ label, first, last, firstDate, lastDate, singleSession = false }: {
  label: string; first: TopTwoConcentration; last: TopTwoConcentration; firstDate: string; lastDate: string; singleSession?: boolean
}) {
  const names = (item: TopTwoConcentration) => item.state === 'available' ? item.sectors.join(', ') : item.state === 'no-coverage' ? 'Sin cobertura' : 'Sin sectores con eventos'
  return <div className="text-xs">
    <p>{label}: {singleSession ? `${concentrationText(last)} (${lastDate})` : `${concentrationText(first)} (${firstDate}) → ${concentrationText(last)} (${lastDate})`}</p>
    <details className="mt-1">
      <summary className="cursor-pointer text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">Sectores incluidos</summary>
      <p className="mt-1 text-muted-foreground">{singleSession ? `${lastDate}: ${names(last)}` : `${firstDate}: ${names(first)} · ${lastDate}: ${names(last)}`}</p>
    </details>
  </div>
}

function EvolutionContent({ result }: { result: Extract<NormalizedSectorEvolution, { state: 'available' }> }) {
  const [selection, setSelection] = useState<{ sector: string | null; dismissed: boolean }>({ sector: null, dismissed: false })
  const panelId = useId()
  const first = result.sessions[0]
  const last = result.sessions[result.sessions.length - 1]
  const selectedExists = selection.sector != null && result.sectors.some(row => row.sector === selection.sector)
  if (selection.sector != null && !selectedExists && !selection.dismissed) {
    setSelection(current => ({ ...current, dismissed: true }))
  }
  const selected = selection.dismissed ? undefined : result.sectors.find(row => row.sector === selection.sector)
  return <>
    <p className="mt-1 text-xs text-muted-foreground">Hasta cinco sesiones almacenadas de SPY · tasas de máximos y mínimos en escala fija 0–100%.</p>
    {result.sessions.length < 2 && <p className="mt-2 text-xs text-amber-300">Hay una sola sesión; las variaciones entre extremos no están disponibles.</p>}
    <div className="mt-3 grid gap-3 border-y border-border py-3 sm:grid-cols-2">
      {(['highs', 'lows'] as const).map(side => {
        const label = side === 'highs' ? 'Sectores con máximos' : 'Sectores con mínimos'
        const firstActivity = result.summary[side].first
        const lastActivity = result.summary[side].last
        const firstConcentration = result.summary.concentration[side].first
        const lastConcentration = result.summary.concentration[side].last
        const activityLabel = (item: { active_sectors: number; eligible_sectors: number }, date: string) => item.eligible_sectors === 0
          ? `Sin cobertura suficiente (${date})` : `${item.active_sectors}/${item.eligible_sectors} (${date})`
        return <div key={side} className="space-y-2 text-muted-foreground">
          <p className="text-xs">{label}: {result.sessions.length === 1
            ? activityLabel(lastActivity, last.date)
            : `${activityLabel(firstActivity, first.date)} → ${activityLabel(lastActivity, last.date)}`}</p>
          {result.sessions.length > 1 && (firstActivity.eligible_sectors === 0 || lastActivity.eligible_sectors === 0) && <p className="text-[10px]">Sin cobertura suficiente para comparar ambos extremos.</p>}
          <Concentration label={side === 'highs' ? 'Concentración top 2 de máximos' : 'Concentración top 2 de mínimos'} first={firstConcentration} last={lastConcentration} firstDate={first.date} lastDate={last.date} singleSession={result.sessions.length === 1} />
        </div>
      })}
    </div>
    {result.sectors.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">Sin sectores elegibles en estas sesiones.</p> : <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[760px] border-y border-border text-left text-xs">
        <caption className="caption-top py-2 text-left text-xs text-muted-foreground">Tasas y cobertura al <span className="whitespace-nowrap">{last.date}</span> · Cambios entre <span className="whitespace-nowrap">{first.date}</span> y <span className="whitespace-nowrap">{last.date}</span></caption>
        <thead><tr className="border-b border-border text-muted-foreground">
          <th scope="col" className="py-2 pr-3">Sector</th>
          <th scope="col" className="px-2 py-2">Máximos</th>
          <th scope="col" className="px-2 py-2">Mínimos</th>
          <th scope="col" className="px-2 py-2">Δ máximos</th>
          <th scope="col" className="px-2 py-2">Δ mínimos</th>
          <th scope="col" className="px-2 py-2">Cobertura</th>
        </tr></thead>
        <tbody>{result.sectors.map(row => {
        const comparison = row.comparison
        const latest = row.points[row.points.length - 1]
        return <tr key={row.sector} className="border-b border-border last:border-0">
          <th scope="row" className="py-2 pr-3 font-medium"><button type="button" aria-expanded={selection.sector === row.sector && !selection.dismissed} aria-controls={panelId} onClick={() => setSelection(current => current.sector === row.sector && !current.dismissed ? { sector: null, dismissed: false } : { sector: row.sector, dismissed: false })} className="text-left underline decoration-border underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">{row.sector}</button></th>
          <td className="px-2 py-2 tabular-nums">{latestRateText(latest, 'high', last.date, false)}</td>
          <td className="px-2 py-2 tabular-nums">{latestRateText(latest, 'low', last.date, false)}</td>
          <td className={`px-2 py-2 tabular-nums ${comparison.state === 'available' ? deltaClass('high', comparison.high_delta_pp) : 'text-muted-foreground'}`}>{comparison.state === 'available' ? `${comparison.high_delta_pp > 0 ? '+' : ''}${comparison.high_delta_pp.toFixed(1)} pp` : `Sin dato · ${comparison.reason}`}</td>
          <td className={`px-2 py-2 tabular-nums ${comparison.state === 'available' ? deltaClass('low', comparison.low_delta_pp) : 'text-muted-foreground'}`}>{comparison.state === 'available' ? `${comparison.low_delta_pp > 0 ? '+' : ''}${comparison.low_delta_pp.toFixed(1)} pp` : `Sin dato · ${comparison.reason}`}</td>
          <td className="px-2 py-2 tabular-nums">{latest ? `${latest.eligible_symbols} elegibles · ${latest.excluded_symbols} excluidas` : `Sin observación (${last.date})`}</td>
        </tr>
      })}</tbody></table>
      <article id={panelId} hidden={!selected} className="border-b border-border bg-background/40 p-3" aria-label={selected ? `Detalle histórico de ${selected.sector}` : 'Detalle histórico del sector seleccionado'}>
        {selected && <>
        <div className="flex items-center justify-between gap-3"><h4 className="text-sm font-medium">Historial de {selected.sector}</h4><button type="button" onClick={() => setSelection({ sector: null, dismissed: false })} className="text-xs text-muted-foreground underline underline-offset-4">Cerrar</button></div>
        {selected.comparison.state === 'available' && <>
          <p className="mt-1 text-[10px] text-muted-foreground">Elegibles {selected.comparison.start.eligible_symbols} → {selected.comparison.end.eligible_symbols} ({selected.comparison.eligible_delta > 0 ? '+' : ''}{selected.comparison.eligible_delta}) · excluidas {selected.comparison.start.excluded_symbols} → {selected.comparison.end.excluded_symbols} ({selected.comparison.excluded_delta > 0 ? '+' : ''}{selected.comparison.excluded_delta}) · {selected.comparison.start.date} → {selected.comparison.end.date}</p>
          {(selected.comparison.eligible_delta !== 0 || selected.comparison.excluded_delta !== 0) && <p className="mt-1 text-[10px] text-amber-300">La cobertura cambió entre las fechas; las poblaciones pueden no coincidir.</p>}
        </>}
        <div className="mt-2 space-y-1"><Sparkline points={selected.points} side="high_rate" sector={selected.sector} /><Sparkline points={selected.points} side="low_rate" sector={selected.sector} /></div>
        <ul className="mt-2 space-y-1 text-[10px] text-muted-foreground">{selected.points.map((point, index) => <li key={result.sessions[index].date}>{point ? `${dateEvidence(point)} · máximos ${percent(point.high_rate)}, mínimos ${percent(point.low_rate)}` : `${result.sessions[index].date}: sin observación para este sector`}</li>)}</ul>
        </>}
      </article>
    </div>}

  </>
}

export default function SectorEvolution({
  result, pending, error, fetching, onRetry,
}: {
  result: NormalizedSectorEvolution | null | undefined
  pending: boolean
  error: boolean
  fetching: boolean
  onRetry: () => void
}) {
  return <section className="rounded border border-border bg-card p-4" aria-labelledby="sector-evolution-title">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 id="sector-evolution-title" className="text-sm font-medium">Evolución de extremos por sector</h3><p className="mt-1 text-xs text-muted-foreground">Incidencia y concentración en hasta cinco sesiones de SPY.</p></div>
      <button type="button" onClick={onRetry} disabled={fetching} className="text-xs text-muted-foreground underline underline-offset-4 disabled:opacity-50">{fetching ? 'Consultando…' : 'Actualizar evolución'}</button>
    </div>
    {pending && <p role="status" className="mt-3 text-sm text-muted-foreground">Cargando evolución sectorial…</p>}
    {error && <p role="alert" className="mt-3 text-xs text-amber-300">No se pudo actualizar la evolución sectorial.{result ? ' Se conserva el último dato recibido.' : ' Podés reintentar desde esta sección.'}</p>}
    {!pending && !error && result == null && <p role="status" className="mt-3 text-sm text-muted-foreground">Este servidor aún no ofrece el historial sectorial. El contexto general sigue disponible.</p>}
    {!pending && result?.state === 'no-reference-session' && <p role="status" className="mt-3 text-sm text-muted-foreground">No hay una sesión almacenada de SPY para la fecha del contexto ({result.as_of}); no se reconstruye una fecha sustituta.</p>}
    {!pending && result?.state === 'unavailable' && <p role="status" className="mt-3 text-sm text-muted-foreground">Evolución sectorial no disponible: {result.reason}</p>}
    {!pending && result?.state === 'available' && <EvolutionContent result={result} />}
    <details className="mt-3 border-t border-border pt-2">
      <summary className="cursor-pointer py-2 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">Metodología y límites</summary>
      <p className="text-xs text-muted-foreground">Cada sesión cuenta un nuevo máximo cuando el máximo intradiario supera el máximo de la sesión anterior del calendario SPY; cuenta un nuevo mínimo cuando el mínimo intradiario queda por debajo del mínimo de esa sesión. Los empates no generan eventos. El calendario refleja sesiones de SPY disponibles, no un calendario bursátil certificado.</p>
      <p className="mt-2 text-xs text-muted-foreground">La atribución sectorial y la capitalización usan metadata actual, no composición histórica. Las poblaciones elegibles pueden cambiar entre sesiones; tasas y variaciones son descriptivas y no implican continuidad, reversión ni recomendación.</p>
    </details>
  </section>
}
