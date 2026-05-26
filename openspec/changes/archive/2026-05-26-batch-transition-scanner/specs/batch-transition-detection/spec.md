## ADDED Requirements

### Requirement: Batch transition scanner over the quality universe

The system SHALL provide a batch scanner that walks the quality-filtered universe of stocks and invokes `TransitionEngine.calculate_operational_transition` for each, persisting any non-STABLE observations.

#### Scenario: Scanner uses QUALITY_FILTERS for universe selection

- **GIVEN** the latest `stock_metrics.date` is `D`
- **WHEN** the scanner is invoked for `as_of_date = D`
- **THEN** it SHALL select the set of symbols whose `stock_metrics` row for date `D` satisfies all conditions in `QUALITY_FILTERS` (avg_volume_10d ≥ 500k, current_price ≥ $5, adr_percent ≥ 2%, adr_percent IS NOT NULL)
- **AND** it SHALL NOT scan symbols outside that set

#### Scenario: Scanner loads previous metrics for each symbol

- **GIVEN** a symbol with a `stock_metrics` row at date `D`
- **WHEN** the scanner processes it
- **THEN** it SHALL also load the most recent `stock_metrics` row for that symbol with `date < D`
- **AND** if no previous row exists, the symbol is skipped (no observation possible without a baseline)

#### Scenario: Scanner persists non-STABLE observations via the transition engine

- **GIVEN** a symbol with valid (current, previous) metrics pair
- **WHEN** `TransitionEngine.calculate_operational_transition` returns a transition ≠ STABLE
- **THEN** the existing `OutcomeTracker.record_observation` flow SHALL create a `transition_observations` row, idempotent on `(symbol, transition_type, date_detected)`

#### Scenario: Scanner returns aggregate stats

- **WHEN** the scanner completes a run
- **THEN** it SHALL return a stats object containing `scanned`, `non_stable_detected`, `recorded`, `errors`, and `duration_sec`

#### Scenario: Scanner is resilient to per-symbol errors

- **GIVEN** a symbol that raises an exception during transition calculation
- **WHEN** the scanner encounters the exception
- **THEN** it SHALL log a WARN, increment `errors` in the stats, and continue with the next symbol
- **AND** it SHALL NOT abort the batch

### Requirement: Scheduler triggers the scanner after each SLOW cycle

The data scheduler SHALL invoke the batch transition scanner as a fire-and-forget task after every successful SLOW metrics-update cycle.

#### Scenario: Scanner fires after SLOW completion

- **GIVEN** a SLOW cycle that completes with `count > 0`
- **WHEN** the cycle finalizes
- **THEN** the scheduler SHALL schedule `_batch_scan_transitions` as `asyncio.create_task`, in parallel with `_evaluate_pending_outcomes`

#### Scenario: Scanner uses an independent DB session

- **WHEN** the scheduler triggers the scanner
- **THEN** the scanner SHALL acquire its own `AsyncSession` from the scheduler's session maker, not share the SLOW cycle's session

### Requirement: Manual scan endpoint for testing and forced runs

The API SHALL expose `POST /api/v1/calibration/scan-now` that triggers the scanner synchronously and returns its stats.

#### Scenario: Manual trigger runs against the latest metrics date

- **GIVEN** no `as_of_date` query parameter
- **WHEN** a client calls `POST /api/v1/calibration/scan-now`
- **THEN** the endpoint SHALL run the scanner with `as_of_date = max(stock_metrics.date)`
- **AND** return the scanner's stats object

#### Scenario: Manual trigger accepts a specific as_of_date

- **GIVEN** an `as_of_date` query parameter (ISO date)
- **WHEN** the client calls the endpoint
- **THEN** the scanner SHALL run for that specific date
- **AND** the response SHALL include the date used in the stats

#### Scenario: Manual trigger returns 404 when no metrics exist

- **GIVEN** the database has no `stock_metrics` rows
- **WHEN** the client calls the endpoint with no `as_of_date`
- **THEN** the endpoint SHALL return HTTP 404 with detail `"No stock_metrics data available"`
