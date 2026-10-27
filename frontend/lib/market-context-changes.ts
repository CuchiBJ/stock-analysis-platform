import { normalizeEvolution, validEvolutionDate } from './market-context-evolution'
import type { Benchmark, MarketOverview, RecordedPostureState, Volatility } from './market-context'

export type ChangeDirection = 'deterioration' | 'improvement' | 'unchanged' | 'unavailable'
export interface SessionChange {
  id: 'posture' | 'participation' | 'leaders' | 'spy' | 'qqq' | 'vix'
  label: string
  direction: ChangeDirection
  summary: string
  evidence: string
}

function finitePositive(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function rounded(value: number, digits: number): number {
  return Number(value.toFixed(digits))
}

function direction(delta: number): ChangeDirection {
  return delta < 0 ? 'deterioration' : delta > 0 ? 'improvement' : 'unchanged'
}

function unavailable(id: SessionChange['id'], label: string, reason: string): SessionChange {
  return { id, label, direction: 'unavailable', summary: 'Sin comparación disponible', evidence: reason }
}

const postureOrder: Record<RecordedPostureState, number> = {
  FUERA: 0, DEFENSIVO: 1, SELECTIVO: 2, NORMAL: 3, AGRESIVO: 4,
}
const postureStates = Object.keys(postureOrder) as RecordedPostureState[]

function validUtcTimestamp(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/.test(value)) return false
  const [hour, minute, second] = value.slice(11, 19).split(':').map(Number)
  return validEvolutionDate(value.slice(0, 10)) && hour < 24 && minute < 60 && second < 60 && Number.isFinite(Date.parse(value))
}

function recordedPostureChange(overview: MarketOverview, dates: [string, string] | null): SessionChange {
  const history = overview.posture_history
  if (!history) return unavailable('posture', 'Postura emitida', 'El servidor no ofrece registros de postura; la comparación histórica comienza con los registros disponibles.')
  if (history.status !== 'available') return unavailable('posture', 'Postura emitida', 'El historial de posturas registradas no está disponible.')
  if (!dates) return unavailable('posture', 'Postura emitida', 'No hay un par de fechas SPY válido para buscar registros exactos.')
  if (!Array.isArray(history.records)) return unavailable('posture', 'Postura emitida', 'La lista de registros de postura no es válida.')
  const [beforeDate, afterDate] = dates
  const relevant = history.records.filter(record => record && (record.date === beforeDate || record.date === afterDate))
  const byDate = new Map<string, typeof relevant>()
  for (const record of relevant) byDate.set(record.date, [...(byDate.get(record.date) ?? []), record])
  const beforeRows = byDate.get(beforeDate) ?? []
  const afterRows = byDate.get(afterDate) ?? []
  if (beforeRows.length !== 1 || afterRows.length !== 1) return unavailable('posture', 'Postura emitida', `Se requiere exactamente un registro para ${beforeDate} y ${afterDate}; recibidos ${beforeRows.length} y ${afterRows.length}.`)
  const before = beforeRows[0]
  const after = afterRows[0]
  if (!postureStates.includes(before.state) || !postureStates.includes(after.state)) return unavailable('posture', 'Postura emitida', 'Un registro contiene un estado de postura desconocido.')
  if (!validUtcTimestamp(before.recorded_at) || !validUtcTimestamp(after.recorded_at)) return unavailable('posture', 'Postura emitida', 'Un registro no contiene una hora UTC válida.')
  if (after.state !== overview.context.posture?.state) return unavailable('posture', 'Postura emitida', 'La postura registrada para la fecha actual no coincide con la postura del contexto recibido.')
  const delta = postureOrder[after.state] - postureOrder[before.state]
  const summary = delta < 0 ? 'Más restrictiva' : delta > 0 ? 'Menos restrictiva' : 'Sin cambio'
  return {
    id: 'posture', label: 'Postura registrada', direction: delta < 0 ? 'deterioration' : delta > 0 ? 'improvement' : 'unchanged', summary,
    evidence: `Últimas posturas observadas por sesión; no representan un cierre oficial: ${before.state} (${beforeDate}, ${before.recorded_at}) → ${after.state} (${afterDate}, ${after.recorded_at}).`,
  }
}

function valueChange(
  id: SessionChange['id'], label: string, previous: number | null, current: number | null,
  beforeDate: string, afterDate: string, digits: number, unit: string,
): SessionChange {
  if (previous == null || current == null || !Number.isFinite(previous) || !Number.isFinite(current)) {
    return unavailable(id, label, 'Falta un valor válido en una de las fechas de referencia.')
  }
  const delta = rounded(current - previous, digits)
  return {
    id, label, direction: direction(delta),
    summary: `${delta > 0 ? '+' : ''}${delta.toFixed(digits)} ${unit}`,
    evidence: `${previous.toFixed(digits)} ${unit} (${beforeDate}) → ${current.toFixed(digits)} ${unit} (${afterDate})`,
  }
}

function benchmarkChange(index: Benchmark | undefined, symbol: 'SPY' | 'QQQ', dates: [string, string] | null): SessionChange {
  if (!dates) return unavailable(symbol.toLowerCase() as 'spy' | 'qqq', symbol, 'SPY no confirma un par de sesiones válido para el contexto.')
  if (!index) return unavailable(symbol.toLowerCase() as 'spy' | 'qqq', symbol, 'Benchmark ausente en la respuesta.')
  if (index.date !== dates[1] || index.previous_date !== dates[0]) {
    return unavailable(symbol.toLowerCase() as 'spy' | 'qqq', symbol, 'Las fechas del benchmark no coinciden exactamente con las sesiones de referencia.')
  }
  if (!finitePositive(index.price) || !finitePositive(index.previous_price)) {
    return unavailable(symbol.toLowerCase() as 'spy' | 'qqq', symbol, 'Falta un cierre positivo válido en una de las sesiones.')
  }
  const delta = rounded((index.price / index.previous_price - 1) * 100, 2)
  return {
    id: symbol.toLowerCase() as 'spy' | 'qqq', label: symbol, direction: direction(delta),
    summary: `${delta > 0 ? '+' : ''}${delta.toFixed(2)}%`,
    evidence: `${index.previous_price.toFixed(2)} (${dates[0]}) → ${index.price.toFixed(2)} (${dates[1]})`,
  }
}

export function summarizeSessionChanges(
  overview: MarketOverview,
  volatility: Volatility | undefined,
  volatilityState: { pending?: boolean; error?: boolean } = {},
): SessionChange[] {
  const asOf = overview.context.as_of
  const spy = overview.indices.find(index => index.symbol === 'SPY')
  const dates: [string, string] | null = spy && validEvolutionDate(asOf) && spy.date === asOf &&
    validEvolutionDate(spy.previous_date) && spy.previous_date < asOf ? [spy.previous_date, asOf] : null
  const points = normalizeEvolution(overview.evolution, asOf)
  const before = dates ? points.find(point => point.date === dates[0]) : undefined
  const after = dates ? points.find(point => point.date === dates[1]) : undefined
  const pairReason = dates ? '' : 'No hay una fecha SPY igual a la fecha del contexto y una sesión previa válida en el historial almacenado.'

  const participation = !dates ? unavailable('participation', 'Participación', pairReason) : !before || !after || before.breadthRatio == null || after.breadthRatio == null
    ? unavailable('participation', 'Participación', 'Falta una observación de participación en una de las dos fechas exactas.')
    : (() => {
      const previous = before.breadthRatio * 100
      const current = after.breadthRatio * 100
      const delta = rounded(current - previous, 2)
      return { id: 'participation' as const, label: 'Participación', direction: direction(delta), summary: `${delta > 0 ? '+' : ''}${delta.toFixed(2)} pp`, evidence: `${previous.toFixed(2)}% (${dates[0]}) → ${current.toFixed(2)}% (${dates[1]})` }
    })()
  const leaders = !dates ? unavailable('leaders', 'Líderes', pairReason) : !before || !after || before.leaderCount == null || after.leaderCount == null
    ? unavailable('leaders', 'Líderes', 'Falta un conteo de líderes en una de las dos fechas exactas.')
    : valueChange('leaders', 'Líderes', before.leaderCount, after.leaderCount, dates[0], dates[1], 0, 'líderes')

  const qqq = overview.indices.find(index => index.symbol === 'QQQ')
  let vixChange: SessionChange
  const vix = volatility?.vix
  if (!vix) {
    vixChange = unavailable('vix', 'VIX', volatilityState.pending ? 'VIX todavía se está cargando.' : volatilityState.error ? 'Falló la consulta de VIX; no hay un dato recibido.' : 'VIX no disponible en la respuesta.')
  } else if (vix.refresh_failed || volatilityState.error) {
    vixChange = unavailable('vix', 'VIX', 'La consulta de VIX falló; el dato en caché se conserva con advertencia y no se usa para comparar.')
  } else if (!dates) {
    vixChange = unavailable('vix', 'VIX', pairReason)
  } else if (vix.date !== dates[1] || vix.previous_date !== dates[0]) {
    vixChange = unavailable('vix', 'VIX', 'Las fechas de VIX no coinciden exactamente con las sesiones de referencia.')
  } else if (!finitePositive(vix.price) || !finitePositive(vix.previous_price)) {
    vixChange = unavailable('vix', 'VIX', 'Falta un cierre VIX positivo válido en una de las sesiones.')
  } else {
    vixChange = valueChange('vix', 'VIX', vix.previous_price, vix.price, dates[0], dates[1], 2, 'pts')
    vixChange.direction = vixChange.direction === 'improvement' ? 'deterioration' : vixChange.direction === 'deterioration' ? 'improvement' : vixChange.direction
    vixChange.summary = `${vixChange.direction === 'deterioration' ? 'Volatilidad aumenta' : vixChange.direction === 'improvement' ? 'Volatilidad disminuye' : 'Sin cambio'} · ${vixChange.summary}`
  }

  const posture = recordedPostureChange(overview, dates)
  const rows = [posture, participation, leaders,
    benchmarkChange(spy, 'SPY', dates), benchmarkChange(qqq, 'QQQ', dates), vixChange]
  const rank: Record<ChangeDirection, number> = { deterioration: 0, improvement: 1, unchanged: 2, unavailable: 3 }
  return rows.map((row, index) => ({ row, index })).sort((a, b) => rank[a.row.direction] - rank[b.row.direction] || a.index - b.index).map(({ row }) => row)
}
