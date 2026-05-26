## ADDED Requirements

### Requirement: Scheduler errors persisted to database

The system SHALL capture exceptions raised by scheduled async tasks and persist them to a `scheduler_errors` table for later inspection.

#### Scenario: Decorator persists exception on raise

- **GIVEN** an async function decorated with `@track_task_errors(task_name="X")`
- **WHEN** that function raises any `Exception`
- **THEN** a row SHALL be inserted into `scheduler_errors` with `task_name="X"`, `exception_type` (the class name), `exception_message` (str of the exception), `traceback`, and `occurred_at=NOW()`
- **AND** the original exception SHALL NOT propagate further (the wrapped task quietly fails)
- **AND** the error SHALL be logged at level ERROR with the full traceback

#### Scenario: Decorator preserves success path

- **GIVEN** a decorated async function that returns normally
- **WHEN** the function completes
- **THEN** no row SHALL be inserted into `scheduler_errors`
- **AND** the original return value SHALL be returned to the caller

#### Scenario: DB write failure is non-fatal

- **GIVEN** a decorated function raises while `scheduler_errors` is unreachable
- **WHEN** the decorator tries to persist
- **THEN** the persistence failure SHALL be logged but NOT raised
- **AND** the wrapped function's original exception SHALL also be logged

### Requirement: Data freshness endpoint

The API SHALL expose `GET /api/v1/health/data-freshness` returning a single JSON snapshot of the data pipeline state.

#### Scenario: Endpoint returns freshness comparison

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `stock_metrics_latest` (ISO date), `stock_price_latest` (ISO date), and `metrics_lag_days` (int = days between the two)
- **AND** `is_stale` SHALL be `true` iff `metrics_lag_days > 0`

#### Scenario: Endpoint reports today and weekday flag

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `today_et` (ISO date in US/Eastern) and `is_weekday` (bool, true Mon-Fri)

#### Scenario: Endpoint exposes recent errors

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `recent_errors_24h` (count of `scheduler_errors` with `occurred_at >= NOW() - 24h`) and `recent_errors` (array of up to 5 most recent within that window, each with `task_name`, `exception_type`, `exception_message`, `occurred_at`)

#### Scenario: Endpoint generates human-readable warnings

- **GIVEN** `is_stale=true`
- **WHEN** the endpoint is called
- **THEN** the response `warnings` array SHALL include `"Stock metrics N days behind stock prices"` (with N substituted)

- **GIVEN** `recent_errors_24h > 0`
- **WHEN** the endpoint is called
- **THEN** the response `warnings` array SHALL include `"X scheduler errors in the last 24h"` (with X substituted)

### Requirement: Frontend health banner

The frontend SHALL render a persistent banner in `DashboardLayout` that surfaces data health problems on every page.

#### Scenario: Banner appears when stale

- **GIVEN** `/api/v1/health/data-freshness` returns `is_stale=true`
- **WHEN** the user opens any page wrapped in `DashboardLayout`
- **THEN** an amber banner SHALL appear at the top of the layout displaying the staleness warning

#### Scenario: Banner appears when scheduler errors exist

- **GIVEN** `recent_errors_24h > 0`
- **WHEN** the user opens any page wrapped in `DashboardLayout`
- **THEN** a red banner SHALL appear at the top of the layout displaying the error count and most-recent error type

#### Scenario: Banner hidden when healthy

- **GIVEN** `is_stale=false` AND `recent_errors_24h=0`
- **WHEN** the user opens any page
- **THEN** the banner SHALL NOT render

#### Scenario: Banner polls for updates

- **WHEN** the banner is mounted
- **THEN** it SHALL fetch `/api/v1/health/data-freshness` on mount AND every 60 seconds thereafter

#### Scenario: Banner is not dismissible

- **WHEN** the banner is rendering
- **THEN** there SHALL NOT be a close/dismiss button
- **AND** the banner SHALL only disappear when the underlying condition resolves

### Requirement: Standalone CLI health check

The system SHALL provide a standalone `scripts/health_check.py` that prints the same data-freshness snapshot for use in cron jobs, CI, or manual operator verification.

#### Scenario: CLI prints snapshot and exits 0 when healthy

- **GIVEN** the pipeline is healthy
- **WHEN** the operator runs `python scripts/health_check.py`
- **THEN** the script SHALL print the snapshot JSON to stdout
- **AND** exit with code 0

#### Scenario: CLI exits non-zero on stale or errored state

- **GIVEN** `is_stale=true` OR `recent_errors_24h > 0`
- **WHEN** the operator runs the script
- **THEN** it SHALL print the snapshot
- **AND** exit with code 1
