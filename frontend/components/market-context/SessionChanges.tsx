import { summarizeSessionChanges } from '@/lib/market-context-changes'
import { validEvolutionDate } from '@/lib/market-context-evolution'
import type { MarketOverview, Volatility } from '@/lib/market-context'

const directionClass = {
  deterioration: 'text-red-400',
  improvement: 'text-green-400',
  unchanged: 'text-muted-foreground',
  unavailable: 'text-muted-foreground',
}

export default function SessionChanges({
  overview, volatility, volatilityPending, volatilityError,
}: {
  overview: MarketOverview
  volatility?: Volatility
  volatilityPending: boolean
  volatilityError: boolean
}) {
  const rows = summarizeSessionChanges(overview, volatility, { pending: volatilityPending, error: volatilityError })
  const spy = overview.indices.find(item => item.symbol === 'SPY')
  const referenceStart = validEvolutionDate(overview.context.as_of) && spy?.date === overview.context.as_of && validEvolutionDate(spy.previous_date) && spy.previous_date < overview.context.as_of
    ? spy.previous_date : null
  const eligible = rows.find(row => row.id === 'participation')?.direction !== 'unavailable'
  return <section aria-labelledby="session-changes-title">
    <h3 id="session-changes-title" className="text-lg font-medium">Qué cambió desde la sesión anterior</h3>
    <p className="mt-1 text-xs text-muted-foreground">{referenceStart ? `Comparación entre ${referenceStart} y ${overview.context.as_of}.` : 'No hay un par de fechas SPY válido para comparar.'} La referencia usa la sesión previa disponible en el historial almacenado de SPY y no un calendario bursátil certificado.</p>
    <ul className="mt-3 divide-y divide-border border-y border-border">
      {rows.map(row => <li key={row.id} className="grid gap-1 py-3 sm:grid-cols-[10rem_1fr] sm:gap-4">
        <span className="text-sm text-muted-foreground">{row.label}</span>
        <div><p className={`text-sm font-medium ${directionClass[row.direction]}`}>{row.summary}</p><p className="mt-1 text-xs text-muted-foreground">{row.evidence}</p></div>
      </li>)}
    </ul>
    <p className="mt-2 text-xs text-muted-foreground">Los cambios son descriptivos y no son recomendaciones. {eligible ? 'La población elegible diaria puede variar; el cambio en líderes no identifica entradas o salidas individuales.' : 'La cobertura diaria puede variar; un dato ausente no implica que no haya habido cambio.'}</p>
    {volatilityPending && <p role="status" className="mt-1 text-xs text-amber-300">La comparación de VIX está pendiente mientras se carga su historial.</p>}
    {volatilityError && <p role="alert" className="mt-1 text-xs text-amber-300">No se pudo actualizar VIX; cualquier dato almacenado se conserva con esta advertencia.</p>}
  </section>
}
