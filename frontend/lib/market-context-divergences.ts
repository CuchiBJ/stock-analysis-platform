import { summarizeSessionChanges, type ChangeDirection, type SessionChange } from './market-context-changes'
import type { MarketOverview } from './market-context'

type IndexId = 'spy' | 'qqq'
type InternalId = 'participation' | 'leaders'

export interface DivergenceFinding {
  id: `${IndexId}-${InternalId}`
  index: string
  internal: string
  direction: 'deterioration' | 'improvement'
  narrative: string
  indexEvidence: string
  internalEvidence: string
}

export interface UnavailableDivergence {
  id: `${IndexId}-${InternalId}`
  label: string
  reason: string
}

export interface MarketDivergences {
  findings: DivergenceFinding[]
  evaluatedCount: number
  total: 4
  unavailable: UnavailableDivergence[]
}

const PAIRS: Array<{ index: IndexId; internal: InternalId; indexLabel: string; internalLabel: string }> = [
  { index: 'spy', internal: 'participation', indexLabel: 'SPY', internalLabel: 'la participación sobre EMA21' },
  { index: 'spy', internal: 'leaders', indexLabel: 'SPY', internalLabel: 'la cantidad de líderes' },
  { index: 'qqq', internal: 'participation', indexLabel: 'QQQ', internalLabel: 'la participación sobre EMA21' },
  { index: 'qqq', internal: 'leaders', indexLabel: 'QQQ', internalLabel: 'la cantidad de líderes' },
]

function isAvailable(direction: ChangeDirection): boolean {
  return direction !== 'unavailable'
}

function opposite(a: ChangeDirection, b: ChangeDirection): boolean {
  return (a === 'improvement' && b === 'deterioration') || (a === 'deterioration' && b === 'improvement')
}

function unavailableReason(row: SessionChange | undefined, label: string): string {
  return row?.evidence ?? `${label}: falta evidencia comparable.`
}

export function summarizeMarketDivergences(overview: MarketOverview): MarketDivergences {
  const changes = summarizeSessionChanges(overview, undefined)
  const byId = new Map(changes.map(row => [row.id, row]))
  const findings: Array<DivergenceFinding & { pairOrder: number }> = []
  const unavailable: UnavailableDivergence[] = []
  let evaluatedCount = 0

  PAIRS.forEach((pair, pairOrder) => {
    const index = byId.get(pair.index)
    const internal = byId.get(pair.internal)
    const id = `${pair.index}-${pair.internal}` as const
    if (!index || !internal || !isAvailable(index.direction) || !isAvailable(internal.direction)) {
      const reasons = [
        !index || !isAvailable(index.direction) ? unavailableReason(index, pair.indexLabel) : null,
        !internal || !isAvailable(internal.direction) ? unavailableReason(internal, pair.internalLabel) : null,
      ].filter((reason): reason is string => reason != null)
      unavailable.push({ id, label: `${pair.indexLabel} / ${pair.internalLabel}`, reason: reasons.join(' ') })
      return
    }

    evaluatedCount += 1
    if (!opposite(index.direction, internal.direction)) return
    const direction = index.direction === 'improvement' ? 'deterioration' : 'improvement'
    const narrative = pair.internal === 'participation'
      ? direction === 'deterioration'
        ? `${pair.indexLabel} avanza mientras la participación sobre EMA21 retrocede.`
        : `${pair.indexLabel} retrocede mientras mejora la participación sobre EMA21.`
      : direction === 'deterioration'
        ? `${pair.indexLabel} avanza mientras disminuye la cantidad de líderes.`
        : `${pair.indexLabel} retrocede mientras aumenta la cantidad de líderes.`
    findings.push({
      id, index: pair.indexLabel, internal: pair.internalLabel, direction, narrative,
      indexEvidence: `${pair.indexLabel}: ${index.summary} · ${index.evidence}`,
      internalEvidence: `${pair.internal === 'participation' ? 'Participación sobre EMA21' : 'Cantidad de líderes'}: ${internal.summary} · ${internal.evidence}`,
      pairOrder,
    })
  })

  findings.sort((a, b) => (a.direction === b.direction ? 0 : a.direction === 'deterioration' ? -1 : 1) || a.pairOrder - b.pairOrder)
  return {
    findings: findings.map(({ id, index, internal, direction, narrative, indexEvidence, internalEvidence }) => ({
      id, index, internal, direction, narrative, indexEvidence, internalEvidence,
    })),
    evaluatedCount, total: 4, unavailable,
  }
}
