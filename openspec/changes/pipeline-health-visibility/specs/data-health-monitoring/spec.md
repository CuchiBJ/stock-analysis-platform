## ADDED Requirements

### Requirement: Pipeline heartbeat persistence

The system SHALL persist the state of each scheduler cycle in a `pipeline_heartbeats` table so that the operator can inspect when each cycle last ran, how long it took, how much of the universe it covered, and whether it succeeded.

#### Scenario: Cycle records heartbeat on success

- **GIVEN** a scheduler cycle named `slow_metrics` finishes processing N symbols in T seconds without exceptions
- **WHEN** the cycle calls `record_cycle(cycle_name="slow_metrics", duration_seconds=T, symbols_processed=N, symbols_expected=E, status="ok")`
- **THEN** the row in `pipeline_heartbeats` with `cycle_name="slow_metrics"` SHALL be upserted with `last_run_at=NOW()`, `last_success_at=NOW()`, `last_duration_seconds=T`, `symbols_processed=N`, `symbols_expected=E`, `status="ok"`, `last_error_message=NULL`

#### Scenario: Cycle records heartbeat on partial completion

- **GIVEN** a cycle finishes but processes fewer symbols than expected (e.g. an API batch failed for some symbols)
- **WHEN** the cycle calls `record_cycle(..., symbols_processed=4000, symbols_expected=6600, status="partial", error_message="Polygon 429 on batch 12")`
- **THEN** the row SHALL be upserted with `status="partial"`, `last_error_message="Polygon 429 on batch 12"`, and `last_run_at=NOW()` but `last_success_at` SHALL NOT be updated (retains previous successful run)

#### Scenario: Cycle records heartbeat on failure

- **GIVEN** a cycle raises an exception caught by `@track_task_errors`
- **WHEN** the wrapping code calls `record_cycle(..., status="failed", error_message=str(exc))` in the exception handler
- **THEN** the row SHALL be upserted with `status="failed"`, `last_error_message=str(exc)`, `last_run_at=NOW()`, and `last_success_at` unchanged

#### Scenario: Heartbeat write failure is non-fatal

- **GIVEN** `record_cycle` is invoked while the database is unreachable
- **WHEN** the helper attempts the upsert
- **THEN** the failure SHALL be logged at level WARNING but SHALL NOT propagate
- **AND** the scheduler loop SHALL continue to the next cycle

### Requirement: Data freshness endpoint exposes heartbeats, coverage, and market state

The `/api/v1/health/data-freshness` endpoint SHALL include three additional top-level fields beyond the existing contract: `pipeline_heartbeats`, `coverage`, and `market_state`.

#### Scenario: Endpoint returns heartbeat list

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `pipeline_heartbeats` as an array of objects, one per row in `pipeline_heartbeats`
- **AND** each object SHALL contain `cycle_name`, `last_run_at` (ISO datetime), `last_success_at` (ISO datetime or null), `last_duration_seconds` (number), `symbols_processed` (int or null), `symbols_expected` (int or null), `status` (`"ok"`|`"partial"`|`"failed"`), `last_error_message` (string or null), and `age_seconds` (int = seconds between `last_run_at` and now)

#### Scenario: Endpoint returns universe coverage

- **WHEN** the endpoint is called
- **THEN** the response SHALL include a `coverage` object with `expected` (count of symbols passing QUALITY_FILTERS with a `StockPrice` row for today ET), `actual` (count of symbols passing QUALITY_FILTERS with a `StockMetrics` row for today ET updated after market open), and `pct` (float 0-100 = `actual/expected*100`, or 0 if `expected=0`)

#### Scenario: Endpoint returns market state

- **WHEN** the endpoint is called
- **THEN** the response SHALL include a `market_state` object with `is_open` (bool), `is_warmup` (bool), `minutes_since_open` (int, negative pre-market, null if not a weekday), and `session_phase` (one of `"pre_market"`, `"warmup"`, `"regular"`, `"after_hours"`, `"closed"`)

#### Scenario: Warmup window flag

- **GIVEN** the current time in US/Eastern is a weekday between 09:30 and 10:30 inclusive
- **WHEN** the endpoint is called
- **THEN** `market_state.is_warmup` SHALL be `true` AND `market_state.session_phase` SHALL be `"warmup"`

- **GIVEN** the current time in US/Eastern is a weekday at 10:31
- **WHEN** the endpoint is called
- **THEN** `market_state.is_warmup` SHALL be `false` AND `market_state.session_phase` SHALL be `"regular"`

#### Scenario: Endpoint remains backwards-compatible

- **WHEN** the endpoint is called
- **THEN** the existing fields `stock_metrics_latest`, `stock_price_latest`, `metrics_lag_days`, `is_stale`, `today_et`, `is_weekday`, `recent_errors_24h`, `recent_errors`, `warnings` SHALL remain present with their current semantics

### Requirement: Frontend pipeline health chip always rendered

The frontend SHALL render a `PipelineHealthChip` component in `DashboardLayout` that is always visible (no condition gates its display), positioned in the header.

#### Scenario: Chip shows coverage percentage and status dot

- **WHEN** the chip mounts and receives a healthy health snapshot
- **THEN** the chip SHALL render a colored status dot, the integer coverage percentage (e.g. `98%`), and SHALL NOT render any warmup badge

#### Scenario: Chip status dot reflects worst-case state

- **GIVEN** the snapshot has `recent_errors_24h > 0` OR any heartbeat with `status="failed"`
- **WHEN** the chip renders
- **THEN** the dot SHALL be red

- **GIVEN** none of the red conditions hold AND (`is_stale=true` OR any heartbeat `status="partial"` OR `coverage.pct < 95` OR `market_state.is_warmup=true`)
- **WHEN** the chip renders
- **THEN** the dot SHALL be amber

- **GIVEN** no red and no amber conditions hold
- **WHEN** the chip renders
- **THEN** the dot SHALL be green

#### Scenario: Chip shows warmup badge during warmup window

- **GIVEN** `market_state.is_warmup=true`
- **WHEN** the chip renders
- **THEN** an amber `WARMUP` badge SHALL appear next to the coverage percentage

#### Scenario: Chip polls health endpoint every 30 seconds

- **WHEN** the chip is mounted
- **THEN** it SHALL fetch `/api/v1/health/data-freshness` on mount AND every 30 seconds thereafter

### Requirement: Frontend pipeline health drawer on chip click

The frontend SHALL render a `PipelineHealthDrawer` (sheet from the right) when the `PipelineHealthChip` is clicked, containing detailed pipeline state with progress bars.

#### Scenario: Drawer shows coverage as horizontal progress bar

- **WHEN** the drawer opens
- **THEN** it SHALL render a horizontal progress bar showing `coverage.actual / coverage.expected` filled to `coverage.pct` percent
- **AND** the bar SHALL display the numeric label `{actual} / {expected} ({pct}%)`

#### Scenario: Drawer lists every cycle with status, age, and progress

- **WHEN** the drawer opens
- **THEN** it SHALL render one row per element of `pipeline_heartbeats`
- **AND** each row SHALL display `cycle_name`, a status dot, `last_run_at` formatted as relative time (e.g. `"2m ago"`), and `last_duration_seconds`
- **AND** rows where `symbols_processed` and `symbols_expected` are both non-null SHALL render a thin horizontal progress bar with `symbols_processed/symbols_expected`

#### Scenario: Drawer shows market state and warmup explanation

- **WHEN** the drawer opens
- **THEN** it SHALL display `market_state.session_phase` and `minutes_since_open`
- **AND** if `market_state.is_warmup=true`, an amber notice SHALL explain: "Durante warmup, métricas dependientes de tick (regime, RS) son ruidosas."

#### Scenario: Drawer surfaces recent errors

- **WHEN** the drawer opens AND `recent_errors_24h > 0`
- **THEN** the drawer SHALL display the list of `recent_errors` (task_name, exception_type, exception_message, relative occurred_at)

#### Scenario: Cycle marked stale by age threshold

- **GIVEN** a heartbeat with `cycle_name="slow_metrics"` and `age_seconds > 3600` (twice the expected 1800s interval)
- **WHEN** the drawer renders that row
- **THEN** the status dot SHALL be amber regardless of the persisted `status` field
- **AND** the row SHALL show a `"stale"` label next to the relative time

### Requirement: Banner and chip coexist

The existing `DataHealthBanner` SHALL continue to render under its existing conditions (stale or recent errors), independently of the chip.

#### Scenario: Both render when conditions trigger

- **GIVEN** `is_stale=true`
- **WHEN** the user opens a page in `DashboardLayout`
- **THEN** both the amber `DataHealthBanner` AND the `PipelineHealthChip` SHALL be present in the DOM

#### Scenario: Only chip renders when healthy

- **GIVEN** `is_stale=false` AND `recent_errors_24h=0`
- **WHEN** the user opens a page
- **THEN** the `PipelineHealthChip` SHALL render (green) AND the `DataHealthBanner` SHALL NOT render
