## ADDED Requirements

### Requirement: System snapshots persisted at entry

Every `JournalTrade` SHALL persist four deterministic snapshots taken from the system engines at the moment the trade is first saved. These snapshots are immutable for the life of the trade and represent the system's objective reading of the market and the symbol at entry.

The four snapshot fields are:

- `regime_at_entry: string | null` — the output of `market_context_engine` for the entry date
- `system_score_at_entry: float | null` — the priority score the system would assign to this (symbol, setup) at entry
- `group_strength_at_entry: string | null` — one of `weak`, `neutral`, `strong` from `group_strength_service`
- `leader_health_at_entry: float | null` — 0-1 score from `leader_health_calculator`

A null value SHALL mean "the underlying engine had no data to compute this", never "the engine was not called".

#### Scenario: Create trade with full snapshot coverage

- **GIVEN** the operator creates a trade for symbol "NBIS" on a date with full `stock_metrics` and regime data available
- **WHEN** `POST /api/v1/journal/trades` returns
- **THEN** the persisted row SHALL have non-null values for all four snapshot fields
- **AND** the response object SHALL include them

#### Scenario: Create trade with partial snapshot coverage

- **GIVEN** the operator creates a trade for a symbol that has metrics but no group classification
- **WHEN** the snapshot service runs
- **THEN** `regime_at_entry`, `system_score_at_entry`, `leader_health_at_entry` SHALL be populated
- **AND** `group_strength_at_entry` SHALL be `null`
- **AND** the trade creation SHALL succeed

#### Scenario: Snapshot service failure is non-fatal

- **GIVEN** the snapshot service raises an unexpected exception (e.g. database error mid-query)
- **WHEN** `POST /api/v1/journal/trades` is processing
- **THEN** the failure SHALL be logged at WARNING level
- **AND** the trade SHALL still be created with all four snapshot fields as `null`
- **AND** the API response SHALL be successful

### Requirement: System score fallback for off-system trades

When a trade has no `linked_observation_id` (because no `transition_observation` exists within ±3 days for the symbol), the snapshot service SHALL compute `system_score_at_entry` on-demand by invoking `setup_priority_engine.score_setup(setup, metrics)` with the symbol's metrics for the entry date.

This rule produces a score even for discretionary trades that fell outside the queue, enabling the operator to ask: "do I enter setups the system scores low?"

#### Scenario: Trade with linked observation uses observation-derived score

- **GIVEN** an observation exists for ("TSLA", 2026-06-04) with a known priority_score
- **WHEN** the operator creates a trade for ("TSLA", 2026-06-05)
- **THEN** `system_score_at_entry` SHALL be the score derived from that observation

#### Scenario: Trade without linked observation falls back to engine

- **GIVEN** no observation exists within ±3 days for ("AAPL", 2026-06-05) but `stock_metrics` exists for that date
- **WHEN** the operator creates a trade with setup="u_and_r"
- **THEN** the snapshot service SHALL invoke `setup_priority_engine.score_setup("u_and_r", metrics)` and persist the result

#### Scenario: No metrics — score is null

- **GIVEN** no `stock_metrics` row exists for (symbol, entry_date)
- **WHEN** the snapshot service runs
- **THEN** `system_score_at_entry` SHALL be `null` (no fabricated score)

### Requirement: Performance Matrix uses regime_at_entry as second axis

The `/journal` page SHALL render the Performance Matrix using `Setup × regime_at_entry` instead of `Setup × context` (the operator-typed field). Trades with `regime_at_entry IS NULL` SHALL appear in a visually-distinct bucket labeled "sin data" rather than blending into a regime they don't belong to.

The operator-typed `context` field SHALL remain accessible in the trade drill-in view but SHALL NOT drive any dashboard aggregation.

#### Scenario: Matrix groups by system regime

- **GIVEN** 10 closed trades with varying `regime_at_entry` (`expansive`, `choppy`, `null`)
- **WHEN** the operator opens `/journal`
- **THEN** the Performance Matrix SHALL show one row per (setup, regime_at_entry) combination present
- **AND** trades with `regime_at_entry=null` SHALL appear in a row labeled "sin data"

#### Scenario: Manual context field removed from create form

- **GIVEN** the operator opens `NewTradeModal`
- **WHEN** the form renders
- **THEN** the `context` dropdown SHALL NOT be visible
- **AND** the backend SHALL accept `POST /journal/trades` payloads without a `context` field
- **AND** the persisted row SHALL have `context='unknown'` as default

### Requirement: Historical backfill via CLI

A CLI script `backend/scripts/backfill_journal_snapshots.py` SHALL exist that, when run, updates all existing `journal_trades` rows where any of the four snapshot fields is `null` by invoking the snapshot service. The script SHALL be idempotent (re-running does not change rows already populated) and SHALL support `--dry-run`.

#### Scenario: Backfill populates trades with available data

- **GIVEN** 34 historical trades with all snapshot fields `null`
- **AND** 20 of them have entry dates with full `stock_metrics` and regime data
- **WHEN** the operator runs `python scripts/backfill_journal_snapshots.py`
- **THEN** at least 20 rows SHALL have non-null snapshots after the run
- **AND** the script SHALL print a summary line: `Updated 20 trades · 14 missing all snapshots`

#### Scenario: Dry-run makes no DB changes

- **GIVEN** the same starting state
- **WHEN** the operator runs `python scripts/backfill_journal_snapshots.py --dry-run`
- **THEN** the script SHALL log what it would update
- **AND** the DB SHALL be unchanged when the script exits

**Implementation**: backend [backend/app/services/journal_snapshot_service.py](../../../backend/app/services/journal_snapshot_service.py) (new); [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py); model [backend/app/models/stock.py](../../../backend/app/models/stock.py); frontend [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) and [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx); CLI [backend/scripts/backfill_journal_snapshots.py](../../../backend/scripts/backfill_journal_snapshots.py) (new); migration `add_journal_system_snapshots.py`.
