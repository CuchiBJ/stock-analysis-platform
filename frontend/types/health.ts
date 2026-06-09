export interface RecentError {
  task_name: string
  exception_type: string
  exception_message: string
  occurred_at: string
}

export type CycleStatus = 'ok' | 'partial' | 'failed'

export interface PipelineHeartbeat {
  cycle_name: string
  last_run_at: string | null
  last_success_at: string | null
  last_duration_seconds: number
  symbols_processed: number | null
  symbols_expected: number | null
  status: CycleStatus
  last_error_message: string | null
  age_seconds: number | null
}

export interface Coverage {
  expected: number
  actual: number
  pct: number
}

export type SessionPhase =
  | 'pre_market'
  | 'warmup'
  | 'regular'
  | 'after_hours'
  | 'closed'

export interface MarketState {
  is_open: boolean
  is_warmup: boolean
  minutes_since_open: number | null
  session_phase: SessionPhase
}

export interface HealthSnapshot {
  as_of: string
  stock_metrics_latest: string | null
  stock_price_latest: string | null
  metrics_lag_days: number | null
  is_stale: boolean
  today_et: string
  is_weekday: boolean
  recent_errors_24h: number
  recent_errors: RecentError[]
  pipeline_heartbeats: PipelineHeartbeat[]
  coverage: Coverage
  market_state: MarketState
  warnings: string[]
}
