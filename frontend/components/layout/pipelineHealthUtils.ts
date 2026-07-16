import type { HealthSnapshot, PipelineHeartbeat } from '@/types/health'

export type ChipColor = 'red' | 'amber' | 'green'

// 2x expected interval — beyond this we treat the cycle as stale regardless of
// its persisted status (the scheduler likely crashed between cycles).
export const CYCLE_STALE_THRESHOLDS_S: Record<string, number> = {
  price: 1800,
  fast_metrics: 600,
  slow_metrics: 3600,
  quality_refresh: 600, // 2x the 5-min cadence
  realtime_discovery: 1200,
  post_close_cycle: 60 * 60 * 26, // post-close fires once per weekday
}

// Cycles that only run on weekdays. Their raw wall-clock age spans the weekend
// by design (Fri after-close → Mon after-close ≈ 64h), so a naive age check
// false-flags them as stale every Monday. For these we measure only elapsed
// WEEKDAY time, which still catches a genuine missed weekday run.
export const WEEKDAY_ONLY_CYCLES: ReadonlySet<string> = new Set(['post_close_cycle'])

// Seconds elapsed between `fromIso` and `now` that fall on weekdays (Mon–Fri),
// excluding weekend time. Walks hour-by-hour (cheap: ~24/day) to sidestep
// DST/timezone edge math; weekend membership uses the runtime-local day.
export function weekdayElapsedSeconds(fromIso: string | null, now: number = Date.now()): number | null {
  if (!fromIso) return null
  const start = new Date(fromIso).getTime()
  if (Number.isNaN(start)) return null
  if (now <= start) return 0
  const HOUR = 3600 * 1000
  let elapsed = 0
  for (let t = start; t < now; t += HOUR) {
    const day = new Date(t).getDay() // 0=Sun .. 6=Sat
    if (day !== 0 && day !== 6) {
      elapsed += Math.min(HOUR, now - t) / 1000
    }
  }
  return Math.floor(elapsed)
}

export function isCycleStaleByAge(hb: PipelineHeartbeat): boolean {
  const threshold = CYCLE_STALE_THRESHOLDS_S[hb.cycle_name]
  if (!threshold) return false
  // Weekday-only cycles: measure weekday-elapsed time so the weekend gap
  // doesn't read as stale, while a real missed weekday run still trips it.
  if (WEEKDAY_ONLY_CYCLES.has(hb.cycle_name)) {
    const weekdayAge = weekdayElapsedSeconds(hb.last_run_at)
    return weekdayAge != null && weekdayAge > threshold
  }
  if (hb.age_seconds == null) return false
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
