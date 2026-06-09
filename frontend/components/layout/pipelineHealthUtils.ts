import type { HealthSnapshot, PipelineHeartbeat } from '@/types/health'

export type ChipColor = 'red' | 'amber' | 'green'

// 2x expected interval — beyond this we treat the cycle as stale regardless of
// its persisted status (the scheduler likely crashed between cycles).
export const CYCLE_STALE_THRESHOLDS_S: Record<string, number> = {
  price: 1800,
  fast_metrics: 600,
  slow_metrics: 3600,
  realtime_discovery: 1200,
  post_close_cycle: 60 * 60 * 26, // post-close fires once per weekday
}

export function isCycleStaleByAge(hb: PipelineHeartbeat): boolean {
  const threshold = CYCLE_STALE_THRESHOLDS_S[hb.cycle_name]
  if (!threshold || hb.age_seconds == null) return false
  return hb.age_seconds > threshold
}

export function computeChipColor(snapshot: HealthSnapshot): ChipColor {
  const anyFailed = snapshot.pipeline_heartbeats.some((h) => h.status === 'failed')
  if (snapshot.recent_errors_24h > 0 || anyFailed) return 'red'

  const anyPartial = snapshot.pipeline_heartbeats.some((h) => h.status === 'partial')
  const anyStaleByAge = snapshot.pipeline_heartbeats.some(isCycleStaleByAge)
  const lowCoverage = snapshot.coverage.pct < 95
  if (
    snapshot.is_stale ||
    anyPartial ||
    anyStaleByAge ||
    lowCoverage ||
    snapshot.market_state.is_warmup
  ) {
    return 'amber'
  }
  return 'green'
}

export function dotClass(color: ChipColor): string {
  if (color === 'red') return 'bg-red-500'
  if (color === 'amber') return 'bg-amber-500'
  return 'bg-emerald-500'
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}
