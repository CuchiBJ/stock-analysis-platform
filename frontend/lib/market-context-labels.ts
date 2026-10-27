export type MarketContextLabelFamily = 'participation' | 'leadership' | 'health' | 'density' | 'continuity'

const labels: Record<MarketContextLabelFamily, Record<string, string>> = {
  participation: { EXPANDING: 'Expansión', STABLE: 'Estable', NARROWING: 'Contracción', COLLAPSING: 'Colapso', UNKNOWN: 'Sin clasificación' },
  leadership: { EXPANDING: 'Expansión', HEALTHY: 'Saludable', NARROWING: 'Contracción', THINNING: 'Adelgazamiento', COLLAPSING: 'Colapso', EXHAUSTED: 'Agotamiento', UNKNOWN: 'Sin clasificación' },
  health: { ROBUST: 'Sólida', RECOVERING: 'En recuperación', FRAGILE: 'Frágil', DAMAGED: 'Dañada', UNKNOWN: 'Sin clasificación' },
  density: { STRONG: 'Fuerte', NORMAL: 'Normal', WEAK: 'Débil', UNKNOWN: 'Sin clasificación' },
  continuity: { PAYING: 'Favorable', MIXED: 'Mixta', NOT_PAYING: 'Desfavorable', UNKNOWN: 'Sin clasificación' },
}

export function marketContextLabel(family: MarketContextLabelFamily, value: string | null | undefined): string {
  if (!value) return 'Sin clasificación'
  return labels[family][value] ?? `Sin clasificación (${value})`
}
