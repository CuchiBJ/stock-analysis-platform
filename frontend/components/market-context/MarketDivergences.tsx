import { summarizeMarketDivergences } from '@/lib/market-context-divergences'
import type { MarketOverview } from '@/lib/market-context'

export default function MarketDivergences({ overview }: { overview: MarketOverview }) {
  const result = summarizeMarketDivergences(overview)
  const coverage = `${result.evaluatedCount} de ${result.total} comparaciones evaluables`
  return <section aria-labelledby="market-divergences-title">
    <h3 id="market-divergences-title" className="text-lg font-medium">Divergencias de la sesión</h3>
    <p className="mt-1 text-xs text-muted-foreground">Compara SPY y QQQ con la participación sobre EMA21 y los líderes entre las dos sesiones almacenadas. Son movimientos opuestos descriptivos; no confirman una reversión ni una tendencia.</p>
    <p className="mt-2 text-xs text-muted-foreground">{coverage}</p>
    {result.evaluatedCount === 0 ? <p role="status" className="mt-3 text-sm text-muted-foreground">Evidencia comparable insuficiente para evaluar movimientos opuestos.</p> : result.findings.length === 0 ? <p role="status" className="mt-3 text-sm text-muted-foreground">{result.evaluatedCount === result.total ? 'No se observan movimientos opuestos en estas cuatro comparaciones.' : `No se observan movimientos opuestos entre ${result.evaluatedCount} ${result.evaluatedCount === 1 ? 'comparación evaluable' : 'comparaciones evaluables'}; las demás no tienen evidencia suficiente.`}</p> : <ul className="mt-3 divide-y divide-border border-y border-border">
      {result.findings.map(finding => <li key={finding.id} className="py-3">
        <p className={`text-sm font-medium ${finding.direction === 'deterioration' ? 'text-red-400' : 'text-muted-foreground'}`}>{finding.narrative}</p>
        <p className="mt-1 text-xs text-muted-foreground">{finding.indexEvidence}</p>
        <p className="mt-1 text-xs text-muted-foreground">{finding.internalEvidence}</p>
      </li>)}
    </ul>}
    <p className="mt-2 text-xs text-muted-foreground">Las poblaciones elegibles pueden variar entre días; los cambios en participación o líderes no identifican entradas y salidas individuales.</p>
    {result.unavailable.length > 0 && <details className="mt-2 border-t border-border pt-2">
      <summary className="cursor-pointer py-2 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">Comparaciones sin evidencia suficiente ({result.unavailable.length})</summary>
      <ul className="divide-y divide-border">
        {result.unavailable.map(item => <li key={item.id} className="py-2 text-xs"><span className="font-medium">{item.label}:</span> <span className="text-muted-foreground">{item.reason}</span></li>)}
      </ul>
    </details>}
  </section>
}
