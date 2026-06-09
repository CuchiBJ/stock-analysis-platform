'use client'

import { AlertTriangle, AlertOctagon } from 'lucide-react'
import { usePipelineHealth } from '@/hooks/usePipelineHealth'

export default function DataHealthBanner() {
  const { data: health } = usePipelineHealth()

  if (!health) return null

  const hasErrors = health.recent_errors_24h > 0
  const isStale = health.is_stale

  if (!hasErrors && !isStale) return null

  const palette = hasErrors
    ? 'border-red-500/40 bg-red-500/10 text-red-300'
    : 'border-amber-500/40 bg-amber-500/10 text-amber-300'

  const Icon = hasErrors ? AlertOctagon : AlertTriangle
  const mostRecent = health.recent_errors[0]

  return (
    <div className={`border-b ${palette}`}>
      <div className="container mx-auto px-4 py-2 flex items-center gap-3 text-xs">
        <Icon className="w-4 h-4 shrink-0" />
        <div className="flex-1 min-w-0">
          {hasErrors && (
            <div className="font-semibold">
              {health.recent_errors_24h} scheduler error{health.recent_errors_24h === 1 ? '' : 's'} in the last 24h
              {mostRecent && (
                <span className="font-normal opacity-75 ml-2">
                  · most recent: <span className="font-mono">{mostRecent.task_name}</span> raised <span className="font-mono">{mostRecent.exception_type}</span>
                </span>
              )}
            </div>
          )}
          {isStale && (
            <div className={hasErrors ? 'opacity-75 mt-0.5' : 'font-semibold'}>
              Stock metrics {health.metrics_lag_days} day{health.metrics_lag_days === 1 ? '' : 's'} behind stock prices
              <span className="font-normal opacity-75 ml-2">
                · metrics @ <span className="font-mono">{health.stock_metrics_latest}</span> · prices @ <span className="font-mono">{health.stock_price_latest}</span>
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
