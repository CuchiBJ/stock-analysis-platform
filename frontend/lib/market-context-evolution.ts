export type EvolutionSeverity = 'clean' | 'mild' | 'severe'
export interface EvolutionInput {
  date: string
  breadth_ratio: number | null
  leader_count: number | null
}
export interface EvolutionPoint {
  date: string
  breadthRatio: number | null
  leaderCount: number | null
}
export interface EvolutionHealthInput {
  date?: string | null
  severity?: unknown
}
export interface EvolutionSession extends EvolutionPoint {
  severity: EvolutionSeverity | null
  hasHealthSession: boolean
}

export function validEvolutionDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day
}

function validBreadth(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null
}

function validLeaderCount(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

function metricDuplicate<T>(values: T[]): T {
  return values.every(value => Object.is(value, values[0])) ? values[0] : null as T
}

export function normalizeEvolution(rows: unknown, asOf: string): EvolutionPoint[] {
  if (!Array.isArray(rows) || !validEvolutionDate(asOf)) return []
  const byDate = new Map<string, { breadth: Array<number | null>; leaders: Array<number | null> }>()
  for (const item of rows) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    if (!validEvolutionDate(row.date) || row.date > asOf) continue
    const entry = byDate.get(row.date) ?? { breadth: [], leaders: [] }
    entry.breadth.push(validBreadth(row.breadth_ratio))
    entry.leaders.push(validLeaderCount(row.leader_count))
    byDate.set(row.date, entry)
  }
  return [...byDate.entries()].sort(([left], [right]) => left.localeCompare(right)).slice(-20).map(([date, values]) => ({
    date,
    breadthRatio: metricDuplicate(values.breadth),
    leaderCount: metricDuplicate(values.leaders),
  }))
}

function recognizedSeverity(value: unknown): EvolutionSeverity | null {
  return value === 'clean' || value === 'mild' || value === 'severe' ? value : null
}

export function joinEvolutionSeverity(points: EvolutionPoint[], health: unknown, asOf: string): EvolutionSession[] {
  const byDate = new Map<string, Array<EvolutionSeverity | null>>()
  if (Array.isArray(health) && validEvolutionDate(asOf)) {
    for (const item of health as EvolutionHealthInput[]) {
      if (!item || !validEvolutionDate(item.date) || item.date > asOf) continue
      const values = byDate.get(item.date) ?? []
      values.push(recognizedSeverity(item.severity))
      byDate.set(item.date, values)
    }
  }
  return points.map(point => {
    const values = byDate.get(point.date)
    return {
      ...point,
      severity: values && values.length > 0 ? metricDuplicate(values) : null,
      hasHealthSession: Boolean(values?.length),
    }
  })
}

export function evolutionSegments<K extends 'breadthRatio' | 'leaderCount'>(
  points: EvolutionPoint[], key: K,
): Array<Array<EvolutionPoint & { value: NonNullable<EvolutionPoint[K]> }>> {
  const segments: Array<Array<EvolutionPoint & { value: NonNullable<EvolutionPoint[K]> }>> = []
  let current: Array<EvolutionPoint & { value: NonNullable<EvolutionPoint[K]> }> = []
  for (const point of points) {
    const value = point[key]
    if (value == null) {
      if (current.length) segments.push(current)
      current = []
      continue
    }
    current.push({ ...point, value })
  }
  if (current.length) segments.push(current)
  return segments
}
