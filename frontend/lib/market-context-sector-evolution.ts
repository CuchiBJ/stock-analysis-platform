export interface SectorEvolutionSector {
  sector: string
  eligible_symbols: number
  excluded_symbols: number
  high_count: number
  low_count: number
}

export interface SectorEvolutionSession {
  date: string
  eligible_symbols: number
  excluded_symbols: number
  high_count: number
  low_count: number
  sectors: SectorEvolutionSector[]
}

export interface SectorEvolutionResponse {
  as_of: string
  status: 'available' | 'no_reference_session'
  sessions: SectorEvolutionSession[]
}

export interface SectorEvolutionPoint {
  date: string
  high_count: number
  low_count: number
  eligible_symbols: number
  excluded_symbols: number
  high_rate: number | null
  low_rate: number | null
}

export type SectorEndpointComparison =
  | { state: 'available'; start: SectorEvolutionPoint; end: SectorEvolutionPoint; high_delta_pp: number; low_delta_pp: number; eligible_delta: number; excluded_delta: number }
  | { state: 'unavailable'; reason: string; start: SectorEvolutionPoint | null; end: SectorEvolutionPoint | null }

export interface SectorEvolutionRow {
  sector: string
  points: Array<SectorEvolutionPoint | null>
  comparison: SectorEndpointComparison
  direction: 'deterioration' | 'improvement' | 'unchanged' | 'unavailable'
}

export interface SideActivity {
  first: { active_sectors: number; eligible_sectors: number }
  last: { active_sectors: number; eligible_sectors: number }
}

export type TopTwoConcentration =
  | { state: 'available'; event_count: number; total_events: number; percent: number; sectors: string[] }
  | { state: 'no-coverage' }
  | { state: 'no-events' }

export interface SectorEvolutionSummary {
  highs: SideActivity
  lows: SideActivity
  concentration: {
    highs: { first: TopTwoConcentration; last: TopTwoConcentration }
    lows: { first: TopTwoConcentration; last: TopTwoConcentration }
  }
}

export type NormalizedSectorEvolution =
  | { state: 'available'; as_of: string; sessions: SectorEvolutionSession[]; sectors: SectorEvolutionRow[]; summary: SectorEvolutionSummary }
  | { state: 'no-reference-session'; as_of: string }
  | { state: 'unavailable'; reason: string }

function validDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function round1(value: number): number {
  return Number(value.toFixed(1))
}

function parseSession(value: unknown): SectorEvolutionSession | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  if (!validDate(item.date) || !count(item.eligible_symbols) || !count(item.excluded_symbols) || !count(item.high_count) || !count(item.low_count) || !Array.isArray(item.sectors)) return null
  const sectors: SectorEvolutionSector[] = []
  const names = new Set<string>()
  for (const raw of item.sectors) {
    if (!raw || typeof raw !== 'object') return null
    const sector = raw as Record<string, unknown>
    if (typeof sector.sector !== 'string' || sector.sector.trim() === '' || names.has(sector.sector) || !count(sector.eligible_symbols) || !count(sector.excluded_symbols) || !count(sector.high_count) || !count(sector.low_count) || sector.high_count > sector.eligible_symbols || sector.low_count > sector.eligible_symbols) return null
    names.add(sector.sector)
    sectors.push({ sector: sector.sector, eligible_symbols: sector.eligible_symbols, excluded_symbols: sector.excluded_symbols, high_count: sector.high_count, low_count: sector.low_count })
  }
  const totals = sectors.reduce((sum, sector) => ({
    eligible: sum.eligible + sector.eligible_symbols,
    excluded: sum.excluded + sector.excluded_symbols,
    highs: sum.highs + sector.high_count,
    lows: sum.lows + sector.low_count,
  }), { eligible: 0, excluded: 0, highs: 0, lows: 0 })
  if (totals.eligible !== item.eligible_symbols || totals.excluded !== item.excluded_symbols || totals.highs !== item.high_count || totals.lows !== item.low_count) return null
  sectors.sort((a, b) => a.sector.localeCompare(b.sector))
  return { date: item.date, eligible_symbols: item.eligible_symbols, excluded_symbols: item.excluded_symbols, high_count: item.high_count, low_count: item.low_count, sectors }
}

function rate(countValue: number, eligible: number): number | null {
  return eligible > 0 ? countValue / eligible : null
}

function makePoint(date: string, item: SectorEvolutionSector | undefined): SectorEvolutionPoint | null {
  if (!item) return null
  return {
    date, high_count: item.high_count, low_count: item.low_count,
    eligible_symbols: item.eligible_symbols, excluded_symbols: item.excluded_symbols,
    high_rate: rate(item.high_count, item.eligible_symbols), low_rate: rate(item.low_count, item.eligible_symbols),
  }
}

function compareSector(points: Array<SectorEvolutionPoint | null>): SectorEndpointComparison {
  const start = points[0] ?? null
  const end = points.at(-1) ?? null
  if (points.length < 2) return { state: 'unavailable', reason: 'Se requieren al menos dos sesiones para comparar.', start, end }
  if (!start || !end) return { state: 'unavailable', reason: 'El sector no tiene observación en ambas fechas de referencia.', start, end }
  if (start.high_rate == null || start.low_rate == null || end.high_rate == null || end.low_rate == null) return { state: 'unavailable', reason: 'El sector no tuvo cobertura positiva en ambas fechas de referencia.', start, end }
  return {
    state: 'available', start, end,
    high_delta_pp: round1((end.high_rate - start.high_rate) * 100),
    low_delta_pp: round1((end.low_rate - start.low_rate) * 100),
    eligible_delta: end.eligible_symbols - start.eligible_symbols,
    excluded_delta: end.excluded_symbols - start.excluded_symbols,
  }
}

function rowDirection(comparison: SectorEndpointComparison): SectorEvolutionRow['direction'] {
  if (comparison.state !== 'available') return 'unavailable'
  const high = comparison.high_delta_pp
  const low = comparison.low_delta_pp
  if (high < 0 || low > 0) return 'deterioration'
  if (high > 0 || low < 0) return 'improvement'
  return 'unchanged'
}

function concentration(session: SectorEvolutionSession, side: 'high_count' | 'low_count'): TopTwoConcentration {
  if (session.eligible_symbols === 0) return { state: 'no-coverage' }
  const total = session[side]
  if (total === 0) return { state: 'no-events' }
  const top = session.sectors.filter(sector => sector[side] > 0).slice().sort((a, b) => b[side] - a[side] || a.sector.localeCompare(b.sector)).slice(0, 2)
  const event_count = top.reduce((sum, sector) => sum + sector[side], 0)
  return { state: 'available', event_count, total_events: total, percent: event_count / total, sectors: top.map(sector => sector.sector) }
}

function makeSummary(sessions: SectorEvolutionSession[]): SectorEvolutionSummary {
  const first = sessions[0]
  const last = sessions[sessions.length - 1]
  const highs = (session: SectorEvolutionSession) => ({
    active_sectors: session.sectors.filter(item => item.eligible_symbols > 0 && item.high_count > 0).length,
    eligible_sectors: session.sectors.filter(item => item.eligible_symbols > 0).length,
  })
  const lows = (session: SectorEvolutionSession) => ({
    active_sectors: session.sectors.filter(item => item.eligible_symbols > 0 && item.low_count > 0).length,
    eligible_sectors: session.sectors.filter(item => item.eligible_symbols > 0).length,
  })
  return {
    highs: { first: highs(first), last: highs(last) },
    lows: { first: lows(first), last: lows(last) },
    concentration: {
      highs: { first: concentration(first, 'high_count'), last: concentration(last, 'high_count') },
      lows: { first: concentration(first, 'low_count'), last: concentration(last, 'low_count') },
    },
  }
}

export function normalizeSectorEvolution(payload: unknown, requestedAsOf: string): NormalizedSectorEvolution {
  if (!validDate(requestedAsOf)) return { state: 'unavailable', reason: 'La fecha del contexto no es válida.' }
  if (!payload || typeof payload !== 'object') return { state: 'unavailable', reason: 'Respuesta de evolución sectorial no disponible.' }
  const raw = payload as Record<string, unknown>
  if (raw.as_of !== requestedAsOf || !Array.isArray(raw.sessions)) return { state: 'unavailable', reason: 'La respuesta no corresponde a la fecha solicitada.' }
  if (raw.status !== 'available' && raw.status !== 'no_reference_session') return { state: 'unavailable', reason: 'Estado de evolución sectorial no reconocido.' }
  if (raw.sessions.length > 5) return { state: 'unavailable', reason: 'La respuesta supera el máximo de cinco sesiones.' }
  if (raw.status === 'no_reference_session') {
    return raw.sessions.length === 0 ? { state: 'no-reference-session', as_of: requestedAsOf } : { state: 'unavailable', reason: 'La respuesta indica ausencia de referencia pero contiene sesiones.' }
  }
  if (raw.sessions.length === 0) return { state: 'unavailable', reason: 'No hay sesiones disponibles en la respuesta.' }
  const sessions: SectorEvolutionSession[] = []
  const dates = new Set<string>()
  for (const item of raw.sessions) {
    const session = parseSession(item)
    if (!session || session.date > requestedAsOf || dates.has(session.date) || (sessions.length > 0 && session.date <= sessions[sessions.length - 1].date)) return { state: 'unavailable', reason: 'Hay fechas, contadores, sectores duplicados o totales que no reconcilian.' }
    dates.add(session.date)
    sessions.push(session)
  }
  if (sessions[sessions.length - 1].date !== requestedAsOf) return { state: 'unavailable', reason: 'La última sesión no coincide con la fecha del contexto.' }

  const sectorNames = [...new Set(sessions.flatMap(session => session.sectors.map(sector => sector.sector)))].sort((a, b) => a.localeCompare(b))
  const sectors = sectorNames.map(sector => {
    const points = sessions.map(session => makePoint(session.date, session.sectors.find(item => item.sector === sector)))
    const comparison = compareSector(points)
    return { sector, points, comparison, direction: rowDirection(comparison) }
  })
  const rank = { deterioration: 0, improvement: 1, unchanged: 2, unavailable: 3 }
  sectors.sort((a, b) => rank[a.direction] - rank[b.direction] || a.sector.localeCompare(b.sector))
  return { state: 'available', as_of: requestedAsOf, sessions, sectors, summary: makeSummary(sessions) }
}
