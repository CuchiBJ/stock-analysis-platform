'use client'

import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useAuth } from '@/components/auth/AuthProvider'
import { ApiError, apiJson } from '@/lib/api-client'
import { benchmarkPriceFreshness, benchmarksComparable, changeText, evidenceDate, evidenceFreshness, numberText, vixFreshnessState, vixPresentation, type Benchmark, type MarketOverview, type Volatility } from '@/lib/market-context'
import { normalizeSectorEvolution } from '@/lib/market-context-sector-evolution'
import ContextEvidence from './ContextEvidence'
import MarketEvolution from './MarketEvolution'
import SectorBreadth from './SectorBreadth'
import SessionChanges from './SessionChanges'
import MarketDivergences from './MarketDivergences'
import SectorEvolution from './SectorEvolution'

const sections = [
  ['lectura-actual', 'Lectura actual'],
  ['cambios-alertas', 'Cambios y alertas'],
  ['indices-volatilidad', 'Índices y volatilidad'],
  ['participacion-sectores', 'Participación y sectores'],
  ['evolucion-continuidad', 'Evolución y continuidad'],
] as const
type SectionId = typeof sections[number][0]

function SectionIndex() {
  const [active, setActive] = useState<SectionId>(sections[0][0])
  useEffect(() => {
    const targets = sections.map(([id]) => document.getElementById(id)).filter((node): node is HTMLElement => Boolean(node))
    let frame = 0
    const updateFromScroll = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const nav = document.querySelector('nav[aria-label="Índice de Market Context"]')
        const navBottom = nav?.getBoundingClientRect().bottom ?? 0
        const atBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2
        const current = atBottom ? targets.at(-1) : [...targets].reverse().find(target => {
          const scrollMargin = Number.parseFloat(getComputedStyle(target).scrollMarginTop) || 0
          return target.getBoundingClientRect().top <= navBottom + scrollMargin + 4
        })
        setActive((current?.id ?? targets[0]?.id ?? sections[0][0]) as SectionId)
      })
    }
    const updateFromHash = () => {
      const id = location.hash.slice(1)
      if (sections.some(([sectionId]) => sectionId === id)) document.getElementById(id)?.scrollIntoView({ block: 'start' })
      updateFromScroll()
    }
    window.addEventListener('scroll', updateFromScroll, { passive: true })
    window.addEventListener('resize', updateFromScroll)
    window.addEventListener('hashchange', updateFromHash)
    if (location.hash) updateFromHash()
    else updateFromScroll()
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll', updateFromScroll); window.removeEventListener('resize', updateFromScroll); window.removeEventListener('hashchange', updateFromHash) }
  }, [])
  return <nav aria-label="Índice de Market Context" className="sticky top-0 z-20 -mx-4 border-y border-border bg-background px-4 py-2 sm:mx-0 sm:rounded sm:border">
    <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs">{sections.map(([id, label]) => <li key={id}><a href={`#${id}`} aria-current={active === id ? 'location' : undefined} onClick={() => setActive(id)} className={`inline-block rounded-sm py-1 underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 ${active === id ? 'font-semibold text-sky-300' : 'text-muted-foreground'}`}>{label}</a></li>)}</ul>
  </nav>
}

function Change({ value, neutral = false }: { value: number | null; neutral?: boolean }) {
  return <span className={`${neutral || value == null || value === 0 ? 'text-muted-foreground' : value > 0 ? 'text-green-400' : 'text-red-400'}`}>{changeText(value)}</span>
}

function BenchmarkView({ index, asOf }: { index: Benchmark; asOf: string }) {
  const priceFreshness = benchmarkPriceFreshness(index.price, index.date, asOf)
  const indicatorFreshness = evidenceFreshness(index.metrics_date, asOf)
  const priceCurrent = priceFreshness === 'current'
  const indicatorLabel = indicatorFreshness === 'current' ? 'Indicadores vigentes para el contexto' : indicatorFreshness === 'earlier' ? 'Indicadores anteriores al contexto' : indicatorFreshness === 'later' ? 'Indicadores posteriores al contexto' : 'Vigencia de indicadores no disponible'
  const priceLabel = priceFreshness === 'earlier' ? 'Dato atrasado' : priceFreshness === 'later' ? 'Precio posterior al contexto; no comparable' : priceFreshness === 'unavailable' ? 'Precio o fecha no disponible; no vigente' : null
  return <article className="py-5 sm:px-5 first:pl-0">
    <h3 className="font-semibold">{index.symbol} <span className="text-xs font-normal text-muted-foreground">· {index.symbol === 'SPY' ? 'S&P 500' : 'Nasdaq 100'}</span></h3>
    <p className="my-2 flex flex-wrap items-baseline gap-3 font-mono tabular-nums"><span className={`text-xl ${priceCurrent ? 'text-muted-foreground' : 'text-muted-foreground/70'}`}>{numberText(index.price)}</span><span className="text-xl font-semibold"><Change value={index.change_pct} neutral={!priceCurrent} /></span></p>
    {priceLabel && <p className="text-xs text-amber-300">{priceLabel}</p>}
    <p className="text-sm">Tendencia {index.trend ?? 'no disponible'}</p>
    <p className="mt-1 text-xs text-muted-foreground">{index.above_ema50 == null ? 'EMA50 sin datos' : `${index.above_ema50 ? 'Sobre' : 'Bajo'} EMA50`} · {index.above_ema200 == null ? 'EMA200 sin datos' : `${index.above_ema200 ? 'Sobre' : 'Bajo'} EMA200`}</p>
    <p className="mt-1 text-xs text-muted-foreground">{index.new_high_52w == null ? 'Máximo de cierres sin datos' : index.new_high_52w ? 'Precio ≥ máximo de cierres (52 semanas)' : 'Precio < máximo de cierres (52 semanas)'}</p>
    <p className="mt-3 text-xs text-muted-foreground">Precio al: {evidenceDate(index.date, asOf)}</p>
    <p className={`text-xs ${indicatorFreshness === 'current' ? 'text-muted-foreground' : 'text-amber-300'}`}>{indicatorLabel}: {evidenceDate(index.metrics_date, asOf)}</p>
  </article>
}

function VixQuoteView({ vix, asOf }: { vix: NonNullable<Volatility['vix']>; asOf: string }) {
  const state = vixFreshnessState(vix.date, asOf, vix.refresh_failed, vix.status)
  return <>
    <p className={`my-2 font-mono ${state.isPreviousClose ? 'text-2xl text-muted-foreground' : 'text-3xl'}`}>{numberText(vix.price)} <span className="text-sm">{changeText(vix.change_points, ' pts')}</span></p>
    <p className="text-sm text-muted-foreground">{changeText(vix.change_pct)} en la sesión</p>
    <p className="mt-3 text-xs text-muted-foreground">Cierre diario: {evidenceDate(vix.date, asOf)}</p>
    {state.isPreviousClose && <p className="text-xs text-muted-foreground">Cierre anterior al contexto</p>}
    <a className="text-xs text-sky-300 hover:underline" href={vix.source_url} target="_blank" rel="noopener noreferrer">Fuente: {vix.source}</a>
    {state.refreshWarning && <p className="text-xs text-amber-300">{state.refreshWarning}</p>}
    {state.dateWarning && <p className="text-xs text-amber-300">{state.dateWarning}</p>}
  </>
}

function VixSpotView({ quote }: { quote: NonNullable<Volatility['current_quote']> }) {
  const observed = new Date(quote.observed_at)
  return <>
    <p className={`my-2 font-mono ${quote.status === 'stale' ? 'text-2xl text-muted-foreground' : 'text-3xl'}`}>{numberText(quote.price)} <span className="text-sm">{changeText(quote.change_points, ' pts')}</span></p>
    <p className="text-sm text-muted-foreground">{changeText(quote.change_pct)} frente al cierre previo</p>
    <p className="mt-3 text-xs text-muted-foreground">Cotización demorada · al menos {quote.delay_minutes} min · observada {Number.isNaN(observed.getTime()) ? 'hora no válida' : `${observed.toISOString().replace('T', ' ').replace('Z', ' UTC')}`}</p>
    {quote.status === 'stale' && <p className="text-xs text-amber-300">Última cotización disponible; dato desactualizado.</p>}
    {quote.refresh_failed && <p className="text-xs text-amber-300">Falló la actualización de la fuente.</p>}
    <p className="text-xs text-muted-foreground">Sesión de cotización: {quote.date}</p>
    <a className="text-xs text-sky-300 hover:underline" href={quote.source_url} target="_blank" rel="noopener noreferrer">Fuente: {quote.source}</a>
  </>
}


export default function MarketContextPage() {
  const { user, status } = useAuth()
  const overview = useQuery({
    queryKey: ['private', user?.id, 'market-context', 'overview'],
    queryFn: async ({ signal }) => {
      try {
        return await apiJson<MarketOverview | null>('/api/v1/market-context/overview', { signal })
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    enabled: status === 'authenticated', staleTime: 60_000, retry: false,
  })
  const asOf = overview.data?.context.as_of
  const volatility = useQuery({
    queryKey: ['private', user?.id, 'market-context', 'volatility', asOf],
    queryFn: ({ signal }) => apiJson<Volatility>(`/api/v1/market-context/volatility?as_of=${encodeURIComponent(asOf!)}`, { signal }),
    enabled: status === 'authenticated' && Boolean(asOf), staleTime: 60_000, refetchInterval: 60_000, retry: false,
  })
  const sectorEvolution = useQuery({
    queryKey: ['private', user?.id, 'market-context', 'sector-evolution', asOf],
    queryFn: async ({ signal }) => {
      try {
        const payload = await apiJson<unknown>(`/api/v1/market-context/sector-evolution?as_of=${encodeURIComponent(asOf!)}`, { signal })
        return normalizeSectorEvolution(payload, asOf!)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    enabled: status === 'authenticated' && Boolean(asOf), staleTime: 60_000, retry: false,
  })
  if (status !== 'authenticated') return null
  const data = overview.data
  const vix = volatility.data?.vix
  const vixDisplay = vixPresentation(volatility.data, data?.context.as_of ?? '')
  return <div className="mx-auto max-w-6xl space-y-7">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-3xl font-semibold">Market context</h1><p className="mt-2 text-sm text-muted-foreground">Lectura del mercado · {asOf ?? 'Última sesión disponible'}{data ? ` · ${data.context.universe_size} acciones` : ''}</p></div><button type="button" disabled={overview.isFetching} onClick={() => void overview.refetch()} className="rounded border border-border px-3 py-2 text-xs disabled:opacity-50">{overview.isFetching ? 'Actualizando…' : 'Actualizar contexto'}</button></header>
    {overview.isPending && <p role="status" className="text-muted-foreground">Cargando contexto del mercado…</p>}
    {overview.isError && <div role="alert" className="rounded border border-amber-400/30 p-3 text-sm text-amber-300">No se pudo actualizar el contexto.{data ? ' Se muestran los últimos datos recibidos, sin actualizar.' : ' Reintentá con Actualizar contexto.'}</div>}
    {!overview.isPending && !overview.isError && !data && <p role="status">Aún no hay contexto disponible para mostrar.</p>}
    {data && <>
      <SectionIndex />
      <section id="lectura-actual" aria-labelledby="lectura-actual-title" className="scroll-mt-24 space-y-3"><h2 id="lectura-actual-title" className="text-xl font-semibold">Lectura actual</h2><ContextEvidence context={data.context} section="posture" /></section>
      <section id="cambios-alertas" aria-labelledby="cambios-alertas-title" className="scroll-mt-24 space-y-4"><h2 id="cambios-alertas-title" className="text-xl font-semibold">Cambios y alertas</h2><SessionChanges overview={data} volatility={volatility.data} volatilityPending={volatility.isPending} volatilityError={volatility.isError} /><MarketDivergences overview={data} /></section>
      <section id="indices-volatilidad" aria-labelledby="indices-volatilidad-title" className="scroll-mt-24"><div className="flex flex-wrap justify-between gap-2"><h2 id="indices-volatilidad-title" className="text-xl font-semibold">Índices y volatilidad</h2><p className="text-xs text-muted-foreground">Variaciones respecto del cierre previo</p></div>
        {!benchmarksComparable(data.indices, data.context.as_of) && <p role="status" className="mt-2 text-xs text-amber-300">SPY y QQQ no son comparables para la sesión del contexto.</p>}
        <div className="mt-3 grid divide-y divide-border border-y border-border sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-[1fr_1fr_0.8fr] lg:divide-x">
          {['SPY', 'QQQ'].map(symbol => <BenchmarkView key={symbol} asOf={data.context.as_of} index={data.indices.find(index => index.symbol === symbol) ?? { symbol, price: null, change_pct: null, date: null, metrics_date: null, trend: null, above_ema50: null, above_ema200: null, new_high_52w: null }} />)}
          <article className="py-5 sm:col-span-2 lg:col-span-1 lg:pl-5"><h3 className="font-semibold">VIX <span className="text-xs font-normal text-muted-foreground">· Volatilidad</span></h3>
            {volatility.isPending ? <p role="status" className="mt-3 text-sm text-muted-foreground">Cargando VIX…</p> : vixDisplay.kind === 'spot' ? <VixSpotView quote={vixDisplay.quote} /> : vixDisplay.kind === 'daily' ? <><p className="mb-1 mt-3 text-xs text-muted-foreground">Cierre diario · cotización de la sesión actual no disponible</p><VixQuoteView vix={vixDisplay.quote} asOf={data.context.as_of} /></> : <div className="mt-3 text-sm text-muted-foreground"><p>VIX no disponible</p>{vixDisplay.earlierSpot && <p className="text-xs">La cotización disponible pertenece a otra sesión.</p>}</div>}
            {volatility.isError && <p role="alert" className="mt-2 text-xs text-amber-300">No se pudo actualizar VIX.{vix ? ' Se muestra el último dato recibido.' : ''}</p>}
            <button type="button" onClick={() => void volatility.refetch()} disabled={volatility.isFetching} className="mt-3 text-xs text-muted-foreground underline underline-offset-4 disabled:opacity-50">{volatility.isFetching ? 'Consultando…' : 'Actualizar VIX'}</button>
          </article>
        </div>
      </section>
      <section id="participacion-sectores" aria-labelledby="participacion-sectores-title" className="scroll-mt-24 space-y-4"><h2 id="participacion-sectores-title" className="text-xl font-semibold">Participación y sectores</h2><ContextEvidence context={data.context} section="participation" /><SectorBreadth data={data.extremes} /><SectorEvolution result={sectorEvolution.data} pending={sectorEvolution.isPending} error={sectorEvolution.isError} fetching={sectorEvolution.isFetching} onRetry={() => void sectorEvolution.refetch()} /><ContextEvidence context={data.context} section="comparisons" /></section>
      <section id="evolucion-continuidad" aria-labelledby="evolucion-continuidad-title" className="scroll-mt-24 space-y-4"><h2 id="evolucion-continuidad-title" className="text-xl font-semibold">Evolución y continuidad</h2><MarketEvolution data={data} /><ContextEvidence context={data.context} section="quality" /></section>
      <ContextEvidence context={data.context} section="additional" />
      <footer className="text-xs text-muted-foreground">Universo operativo: {data.context.universe_size} acciones · Contexto al {data.context.as_of}{data.context.engines_pending.length > 0 && <p className="mt-1">Motores pendientes: {data.context.engines_pending.join(' · ')}</p>}</footer>
    </>}
  </div>
}
