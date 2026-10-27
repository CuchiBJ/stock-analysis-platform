import type { MarketContextData } from '@/components/dashboard/MarketContextBar'
import { explainMarketPosture, type EvidenceStatus, type PostureGate } from '@/lib/market-context-explanation'

const statusLabel: Record<EvidenceStatus, string> = {
  satisfied: 'Cumplida',
  pending: 'Pendiente',
  unknown: 'Sin datos',
}
const statusColor: Record<EvidenceStatus, string> = {
  satisfied: 'text-foreground',
  pending: 'text-amber-400',
  unknown: 'text-muted-foreground',
}
const stateColor: Record<string, string> = {
  FUERA: 'border-red-400/70',
  DEFENSIVO: 'border-amber-400/70',
  SELECTIVO: 'border-amber-400/70',
  NORMAL: 'border-border',
  AGRESIVO: 'border-border',
}

function GateList({ title, gates }: { title: string; gates: PostureGate[] }) {
  return <section className="mt-4">
    <h4 className="text-sm font-medium">{title}</h4>
    <ul className="mt-1 divide-y divide-border">
      {gates.map(item => <li key={item.label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2 text-sm">
        <span>{item.label}</span>
        <span className={statusColor[item.status]}>{statusLabel[item.status]} · <span className="font-mono tabular-nums">{item.evidence}</span></span>
      </li>)}
    </ul>
  </section>
}

export default function PostureExplanation({ context }: { context: MarketContextData }) {
  const model = explainMarketPosture(context)
  const posture = context.posture
  const state = posture?.state ?? 'Sin datos'
  const border = stateColor[state] ?? 'border-border'
  const instruction = state === 'FUERA'
    ? 'Sin compras nuevas — postura restrictiva del sistema.'
    : posture?.instruction

  return <section className={`border-l-2 ${border} bg-card px-4 py-3`}>
    <h3 className={`text-lg font-semibold ${state === 'FUERA' ? 'text-red-400' : state === 'DEFENSIVO' || state === 'SELECTIVO' ? 'text-amber-400' : 'text-foreground'}`}>{state}</h3>
    {instruction && <p className="mt-1 text-sm">{instruction}</p>}
    <div className="mt-3 space-y-1 text-sm leading-relaxed">
      {model.summary.map((sentence, index) => <p key={index}>{sentence}</p>)}
    </div>
    <p className="mt-2 text-sm text-muted-foreground">{model.currentDamage}</p>
    {model.continuity && <p className="mt-2 text-sm">{model.continuity}</p>}
    <details className="mt-3 border-t border-border pt-2">
      <summary className="cursor-pointer py-2 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">Evidencia y condiciones de reparación</summary>
      <dl className="divide-y divide-border">
        {model.rows.map(row => <div key={row.label} className="grid gap-1 py-2 text-sm sm:grid-cols-[8rem_1fr] sm:gap-3">
          <dt className="text-muted-foreground">{row.label}</dt>
          <dd className="font-mono tabular-nums">{row.value}</dd>
        </div>)}
      </dl>
      {model.repairGates.length > 0 && <>
        <GateList title="Reparación de salud" gates={model.repairGates} />
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">La reparación de salud no garantiza una mejora de postura; siguen vigentes los niveles y la continuidad.</p>
      </>}
      {model.earlyGates.length > 0 && <>
        <GateList title="Acceso anticipado a SELECTIVO" gates={model.earlyGates} />
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">Las confirmaciones o excepciones no anulan las protecciones ni conceden NORMAL o AGRESIVO.</p>
      </>}
      {model.audit && <details className="mt-3 border-t border-border pt-2">
        <summary className="cursor-pointer py-2 text-xs text-muted-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400">Respuesta original del sistema · auditoría</summary>
        <pre className="max-h-96 overflow-auto rounded border border-border bg-background p-3 text-xs leading-relaxed text-muted-foreground">{JSON.stringify(model.audit, null, 2)}</pre>
      </details>}
    </details>
  </section>
}
