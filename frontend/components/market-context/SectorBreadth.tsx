'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import { type Constituent, type MarketOverview, type SectorConstituents } from '@/lib/market-context'
import { incidenceRate, sectorRate, sectorTotals, sortSectors, type SectorConcentration, type SectorRate, type SectorSort } from '@/lib/market-context-sectors'

const summaryStyle = 'cursor-pointer py-3 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400'

function percent(ratio: number) { return `${(ratio * 100).toFixed(1)}%` }

function Concentration({ label, result }: { label: string; result: SectorConcentration }) {
  if (result.state === 'no-events') return <p>{label}: sin eventos</p>
  if (result.state === 'incomplete') return <p>{label}: detalle incompleto; concentración no calculada</p>
  return <p>{label}: {result.sectors.join(', ')} reúnen {result.count}/{result.total} ({percent(result.percent)}) de los eventos</p>
}

function rateLabel(rate: SectorRate) {
  if (rate.state === 'no-coverage') return 'Sin cobertura suficiente'
  if (rate.state === 'unavailable') return 'Cobertura no disponible'
  return `${rate.count}/${rate.eligible} (${percent(rate.ratio)})`
}

function RateBar({ rate, side }: { rate: SectorRate; side: 'highs' | 'lows' }) {
  const available = rate.state === 'available'
  return <div className={`flex h-2 overflow-hidden bg-muted ${side === 'lows' ? 'justify-end rounded-l' : 'rounded-r'}`} aria-hidden="true">
    {available && <span className={`h-full ${side === 'lows' ? 'bg-red-400' : 'bg-green-400'}`} style={{ width: `${rate.ratio * 100}%` }} />}
  </div>
}

function StockList({ stocks, title }: { stocks: Constituent[]; title: string }) {
  return <div><h4 className="mb-2 text-xs text-muted-foreground">{title}</h4>
    {stocks.length === 0 ? <p className="text-xs text-muted-foreground">Sin eventos en esta sesión</p> : <ul className="space-y-2">{stocks.map(stock => <li key={stock.symbol} className="flex items-baseline justify-between gap-3 text-sm"><Link className="font-mono text-sky-300 underline-offset-4 hover:underline" href={`/stock/${encodeURIComponent(stock.symbol)}`}>{stock.symbol}</Link><span className="text-right text-xs text-muted-foreground">{stock.name ?? 'Nombre no disponible'}</span></li>)}</ul>}
  </div>
}

function SectorRow({ sector }: { sector: SectorConstituents }) {
  const highRate = sectorRate(sector, 'highs')
  const lowRate = sectorRate(sector, 'lows')
  const eligible = Number.isInteger(sector.eligible_symbols) && (sector.eligible_symbols ?? -1) >= 0
  const excluded = Number.isInteger(sector.excluded_symbols) && (sector.excluded_symbols ?? -1) >= 0
  return <article className="grid gap-2 border-t border-border py-2 sm:grid-cols-[minmax(10rem,0.8fr)_minmax(0,1.3fr)] sm:items-center">
    <div>
      <details>
        <summary className={`${summaryStyle} flex flex-wrap items-center gap-x-2 py-1`}><span>{sector.sector}</span><span className="text-[10px] text-sky-300">Ver acciones</span></summary>
        <div className="grid gap-4 py-3 sm:grid-cols-2"><StockList stocks={sector.highs} title="Nuevos máximos" /><StockList stocks={sector.lows} title="Nuevos mínimos" /></div>
      </details>
      <p className="text-[10px] text-muted-foreground">{eligible ? `${sector.eligible_symbols} elegibles` : 'Cobertura no disponible'}{excluded ? ` · ${sector.excluded_symbols} excluidas` : ''}</p>
    </div>
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-3 gap-y-1 text-[10px]">
      <span className="text-right text-red-400">{sector.lows.length} mínimos · {rateLabel(lowRate)}</span><span className="text-green-400">{sector.highs.length} máximos · {rateLabel(highRate)}</span>
      <div className="col-span-2 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-1" role="img" aria-label={`Escala fija 0–100%; mínimos ${rateLabel(lowRate)}; máximos ${rateLabel(highRate)}`}>
        <RateBar rate={lowRate} side="lows" /><RateBar rate={highRate} side="highs" />
      </div>
      <span className="text-right text-muted-foreground">Mínimos ← 0–100%</span><span className="text-muted-foreground">0–100% → Máximos</span>
    </div>
  </article>
}

export default function SectorBreadth({ data }: { data: MarketOverview['extremes'] }) {
  const [sort, setSort] = useState<SectorSort>('events')
  const sectors = useMemo(() => sortSectors(data.sectors, sort), [data.sectors, sort])
  const totals = sectorTotals(data)
  const highRate = incidenceRate(data.up_count, data.eligible_symbols)
  const lowRate = incidenceRate(data.down_count, data.eligible_symbols)
  const eligible = highRate.state === 'available' && lowRate.state === 'available'
  const noEvents = eligible && data.up_count === 0 && data.down_count === 0
  const eventRatio = eligible && data.up_count + data.down_count > 0 ? data.up_count / (data.up_count + data.down_count) : null

  return <section className="rounded border border-border bg-card p-4" aria-label="Extremos intradiarios comparados con la rueda previa">
    <h3 className="text-sm font-medium">Extremos de la sesión</h3>
    <p className="mt-1 text-xs text-muted-foreground">Máximos y mínimos intradiarios respecto de la rueda previa; no son máximos de 52 semanas.</p>
    <div className="my-3 flex flex-wrap items-baseline gap-6">
      <span><b className="mr-2 font-mono text-3xl font-normal text-green-400">{highRate.state === 'available' ? data.up_count : '—'}</b>máximos · {highRate.state === 'available' ? `${data.up_count}/${highRate.eligible} (${percent(highRate.ratio)} de elegibles)` : highRate.state === 'no-coverage' ? 'Sin cobertura suficiente' : 'Cobertura no disponible'}</span>
      <span><b className="mr-2 font-mono text-3xl font-normal text-red-400">{lowRate.state === 'available' ? data.down_count : '—'}</b>mínimos · {lowRate.state === 'available' ? `${data.down_count}/${lowRate.eligible} (${percent(lowRate.ratio)} de elegibles)` : lowRate.state === 'no-coverage' ? 'Sin cobertura suficiente' : 'Cobertura no disponible'}</span>
    </div>
    {noEvents && <p className="mb-3 text-xs text-muted-foreground">Sin eventos en esta sesión</p>}
    <p className="text-xs text-muted-foreground">Sesión {data.date ?? 'Fecha no disponible'} · {Number.isInteger(data.eligible_symbols) && data.eligible_symbols >= 0 ? data.eligible_symbols : 'Cobertura no disponible'} elegibles · {Number.isInteger(data.excluded_symbols) && data.excluded_symbols >= 0 ? data.excluded_symbols : 'Cobertura no disponible'} excluidas · comparación con la rueda previa disponible</p>
    <div className="my-3 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2"><Concentration label="Concentración de máximos" result={totals.highs} /><Concentration label="Concentración de mínimos" result={totals.lows} /></div>
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-medium">Sectores</h4>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">Ordenar sectores
        <select aria-label="Ordenar sectores" value={sort} onChange={event => setSort(event.target.value as SectorSort)} className="rounded border border-border bg-background px-2 py-1 text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">
          <option value="events">Eventos</option><option value="high-rate">% máximos</option><option value="low-rate">% mínimos</option>
        </select>
      </label>
    </div>
    {sectors.length === 0 ? <p className="py-2 text-sm text-muted-foreground">{data.eligible_symbols === 0 ? 'Sin cobertura suficiente para identificar acciones.' : 'Sin acciones haciendo nuevos extremos en esta sesión.'}</p> : <div>{sectors.map(sector => <SectorRow key={sector.sector} sector={sector} />)}</div>}
    <details className="mt-3 border-t border-border">
      <summary className={summaryStyle}>Metodología y notas</summary>
      <p className="text-xs text-muted-foreground">El máximo intradiario debe superar el máximo de la sesión anterior del calendario SPY; el mínimo intradiario debe caer por debajo del mínimo de esa sesión. Los empates no generan eventos. Si faltan datos de alguna de las dos sesiones, la acción queda excluida.</p>
      <p className="mt-2 text-xs text-muted-foreground">Cada tasa sectorial usa sus acciones elegibles como denominador y una escala fija de 0–100%. La concentración expresa la parte de los eventos atribuida a los sectores con más eventos; no representa el porcentaje del mercado ni fuerza sectorial.</p>
      <p className="mt-2 text-xs text-muted-foreground">Una acción puede registrar ambos extremos en la misma sesión y cuenta una vez por lado. La metadata sectorial refleja la clasificación disponible actualmente; no representa necesariamente la composición histórica.</p>
      {eventRatio != null && <p className="mt-2 text-xs text-muted-foreground">El ratio entre eventos es {percent(eventRatio)} de máximos sobre el total de máximos y mínimos; no es una tasa sobre el universo.</p>}
    </details>
  </section>
}
