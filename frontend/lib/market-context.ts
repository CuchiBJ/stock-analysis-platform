import type { MarketContextData } from '../components/dashboard/MarketContextBar'

export interface Benchmark {
  symbol: string
  price: number | null
  change_pct: number | null
  date: string | null
  previous_date?: string | null
  previous_price?: number | null
  metrics_date: string | null
  trend: string | null
  above_ema50: boolean | null
  above_ema200: boolean | null
  new_high_52w: boolean | null
}
export interface Constituent { symbol: string; name: string | null }
export interface SectorConstituents {
  sector: string
  highs: Constituent[]
  lows: Constituent[]
  /** Optional for compatibility with overview responses generated before sector coverage shipped. */
  eligible_symbols?: number
  /** Optional for compatibility with overview responses generated before sector coverage shipped. */
  excluded_symbols?: number
}
export interface MarketEvolutionRow {
  date: string
  breadth_ratio: number | null
  leader_count: number | null
}
export type RecordedPostureState = 'FUERA' | 'DEFENSIVO' | 'SELECTIVO' | 'NORMAL' | 'AGRESIVO'
export interface RecordedPosture {
  date: string
  state: RecordedPostureState
  instruction: string
  recorded_at: string
}
export interface PostureHistory {
  status: 'available' | 'unavailable'
  records: RecordedPosture[]
}
export interface MarketOverview {
  context: MarketContextData
  indices: Benchmark[]
  evolution?: MarketEvolutionRow[]
  /** Optional for compatibility with servers predating recorded posture history. */
  posture_history?: PostureHistory
  extremes: {
    date: string | null
    up_count: number
    down_count: number
    eligible_symbols: number
    excluded_symbols: number
    up_ratio: number | null
    sectors: SectorConstituents[]
  }
}
export interface Volatility {
  vix: {
    symbol: string; price: number; change_points: number | null; change_pct: number | null
    date: string; previous_date?: string | null; previous_price?: number | null; source: string; source_url: string; status: 'current' | 'stale'; refresh_failed?: boolean
  } | null
  current_quote?: {
    symbol: string; price: number; previous_close: number; change_points: number; change_pct: number
    date: string; observed_at: string; fetched_at: string; source: string; source_url: string
    delay_minutes: number; status: 'current' | 'stale'; refresh_failed: boolean
  } | null
}

export function vixPresentation(volatility: Volatility | null | undefined, asOf: string) {
  const current = volatility?.current_quote
  if (current && evidenceFreshness(current.date, asOf) === 'current') return { kind: 'spot' as const, quote: current }
  if (volatility?.vix) return { kind: 'daily' as const, quote: volatility.vix, earlierSpot: Boolean(current) }
  return { kind: 'unavailable' as const, earlierSpot: Boolean(current) }
}
export type EvidenceFreshness = 'current' | 'earlier' | 'later' | 'unavailable'

function validIsoDate(value: string | null | undefined): boolean {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day
}

export function evidenceFreshness(date: string | null | undefined, asOf: string | null | undefined): EvidenceFreshness {
  if (!validIsoDate(date) || !validIsoDate(asOf)) return 'unavailable'
  if (date === asOf) return 'current'
  return date! < asOf! ? 'earlier' : 'later'
}

export function benchmarkPriceFreshness(price: number | null | undefined, date: string | null | undefined, asOf: string | null | undefined): EvidenceFreshness {
  if (price == null || !Number.isFinite(price)) return 'unavailable'
  return evidenceFreshness(date, asOf)
}

export function benchmarksComparable(indices: Benchmark[], asOf: string): boolean {
  const spy = indices.find(index => index.symbol === 'SPY')
  const qqq = indices.find(index => index.symbol === 'QQQ')
  return Boolean(spy && qqq && benchmarkPriceFreshness(spy.price, spy.date, asOf) === 'current' && benchmarkPriceFreshness(qqq.price, qqq.date, asOf) === 'current')
}

export function vixFreshnessState(date: string | null | undefined, asOf: string, refreshFailed?: boolean, status?: 'current' | 'stale') {
  const freshness = evidenceFreshness(date, asOf)
  const refreshWarning = refreshFailed === true
    ? 'Falló la actualización de la fuente'
    : refreshFailed == null && status === 'stale'
      ? 'Actualización no confirmada'
      : null
  return {
    freshness,
    isPreviousClose: freshness === 'earlier',
    refreshWarning,
    dateWarning: freshness === 'later' ? 'VIX posterior al contexto; no comparable' : freshness === 'unavailable' ? 'Fecha de VIX no válida; no comparable' : null,
  }
}
export function numberText(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? 'Sin datos' : value.toFixed(digits)
}
export function changeText(value: number | null | undefined, unit = '%'): string {
  return value == null || !Number.isFinite(value) ? 'Sin datos' : `${value > 0 ? '+' : ''}${value.toFixed(2)}${unit}`
}
export function percentText(value: number | null | undefined): string {
  return value == null ? 'Sin datos' : `${numberText(value * 100, 1)}%`
}
export function breadthStatus(measure: { eligible_symbols: number; up_count: number; down_count: number; up_ratio: number | null }): string {
  if (measure.eligible_symbols === 0) return 'Sin cobertura suficiente'
  if (measure.up_count + measure.down_count === 0) return 'Sin eventos en esta sesión'
  return `${percentText(measure.up_ratio)} positivos entre eventos`
}
export function evidenceDate(date: string | null, asOf: string): string {
  const freshness = evidenceFreshness(date, asOf)
  if (freshness === 'unavailable') return 'Fecha no disponible'
  if (freshness === 'earlier') return `${date} · Dato anterior al contexto`
  if (freshness === 'later') return `${date} · Fecha posterior al contexto`
  return date!
}
