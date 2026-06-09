## ADDED Requirements

### Requirement: Immutable initial stop price

Every `JournalTrade` SHALL persist an `initial_stop_price: float | null` column representing the first stop loss the operator set for the position. Once set to a non-null value, this column SHALL NOT be modified by any future endpoint operation.

When a trade is created via `POST /journal/trades` and the payload includes a `stop_price`, the system SHALL persist `initial_stop_price = stop_price` at creation time.

When a trade was created without a stop and the operator later adds one via `PATCH /journal/trades/{id}`, the system SHALL set `initial_stop_price = new stop_price` on that PATCH **only if** `initial_stop_price` was previously null.

#### Scenario: POST with stop sets initial_stop_price

- **GIVEN** the operator creates a trade with payload `{entry_price: 100, stop_price: 95, qty: 10, ...}`
- **WHEN** the endpoint processes the request
- **THEN** the persisted row SHALL have `initial_stop_price = 95` and `stop_price = 95`

#### Scenario: PATCH adds first stop sets initial_stop_price

- **GIVEN** a trade with `entry_price=100, stop_price=null, initial_stop_price=null`
- **WHEN** the operator sends `PATCH /journal/trades/{id}` with `{stop_price: 95}`
- **THEN** the row SHALL be updated to `stop_price=95` AND `initial_stop_price=95`

#### Scenario: Subsequent PATCH does NOT modify initial_stop_price

- **GIVEN** a trade with `entry_price=100, stop_price=95, initial_stop_price=95`
- **WHEN** the operator sends `PATCH /journal/trades/{id}` with `{stop_price: 100}` (moving stop to BE)
- **THEN** the row SHALL be updated to `stop_price=100` AND `initial_stop_price=95` (unchanged)

### Requirement: Stop change events are auto-recorded

Every modification of `stop_price` SHALL produce one row in `journal_stop_events` with the auto-classified kind. The system SHALL NOT require operator input to label the change.

The classification rules SHALL be:

- `old is null` AND `new is not null` → `initial`
- `old is not null` AND `new is null` → `removed`
- `new >= entry_price` (with tolerance 1e-6) → `moved_to_be`
- `new > old` (long trade convention) → `trailed_up`
- `new < old` → `widened`
- `new == old` → no event recorded

#### Scenario: Initial event at create time

- **GIVEN** `POST /journal/trades` with `stop_price=95`
- **WHEN** the trade is persisted
- **THEN** exactly one `journal_stop_events` row SHALL exist for this trade with `kind='initial'`, `old_stop_price=null`, `new_stop_price=95`, `auto_classified=true`

#### Scenario: Move-to-BE auto-detected

- **GIVEN** a trade with `entry_price=100, stop_price=95`
- **WHEN** the operator PATCHes `stop_price=100`
- **THEN** a new `journal_stop_events` row SHALL exist with `kind='moved_to_be'`, `old=95`, `new=100`

#### Scenario: Trail-up auto-detected

- **GIVEN** a trade with `entry_price=100, stop_price=95`
- **WHEN** the operator PATCHes `stop_price=97`
- **THEN** a new event SHALL be recorded with `kind='trailed_up'`, `old=95`, `new=97`

#### Scenario: Widen auto-detected (risk increase)

- **GIVEN** a trade with `entry_price=100, stop_price=95`
- **WHEN** the operator PATCHes `stop_price=93` (widening risk)
- **THEN** a new event SHALL be recorded with `kind='widened'`, `old=95`, `new=93`

#### Scenario: No-op PATCH records nothing

- **GIVEN** a trade with `stop_price=95`
- **WHEN** the operator PATCHes `stop_price=95` (same value)
- **THEN** no new `journal_stop_events` row SHALL be created

### Requirement: R-multiple uses initial_stop_price when available

The on-demand `r_multiple` derivation SHALL use `initial_stop_price` as the risk denominator when present. This preserves the institutional convention that R-multiple compares outcome against **planned** risk, not against the operator's risk-management adjustments mid-trade.

When `initial_stop_price` is null (historical trades or trades created without stop), the derivation SHALL fall back to `stop_price` for backward compatibility.

When neither is available, `r_multiple` SHALL be null.

#### Scenario: R-multiple uses initial after stop moved to BE

- **GIVEN** a closed trade with `entry_price=100, exit_price=110, initial_stop_price=95, stop_price=100`
- **WHEN** `_trade_to_dict` builds the response
- **THEN** `r_multiple` SHALL be `(110 - 100) / (100 - 95) = 2.0` (using initial_stop_price)
- **AND** NOT `(110 - 100) / (100 - 100)` which would be divide-by-zero

#### Scenario: Historical trade without initial_stop falls back

- **GIVEN** a CSV-imported trade with `entry_price=100, exit_price=110, stop_price=95, initial_stop_price=null`
- **WHEN** the response is built
- **THEN** `r_multiple` SHALL be `(110 - 100) / (100 - 95) = 2.0` (fallback to stop_price)

### Requirement: is_risk_free derived flag

The trade response SHALL include a derived boolean `is_risk_free` indicating whether the current `stop_price` would protect at least the entry capital.

- `is_risk_free = true` when both `stop_price` and `entry_price` are non-null and `stop_price >= entry_price` (long convention).
- `is_risk_free = false` otherwise.

This flag drives the Open Positions UI badge that visually marks managed-to-BE positions.

#### Scenario: Risk-free open position

- **GIVEN** a trade with `entry_price=100, stop_price=100`
- **WHEN** the response is built
- **THEN** `is_risk_free` SHALL be `true`

#### Scenario: Trade with original stop below entry

- **GIVEN** a trade with `entry_price=100, stop_price=95`
- **WHEN** the response is built
- **THEN** `is_risk_free` SHALL be `false`

#### Scenario: Trade without stop

- **GIVEN** a trade with `stop_price=null`
- **WHEN** the response is built
- **THEN** `is_risk_free` SHALL be `false` (cannot be risk-free without an active stop)

### Requirement: Stop-history endpoint

The system SHALL expose `GET /api/v1/journal/trades/{trade_id}/stop-history` that returns the chronological list of stop events for the specified trade.

The response SHALL be `{ "events": [...] }` where each event includes `id`, `old_stop_price`, `new_stop_price`, `kind`, `occurred_at` (ISO timestamp), `auto_classified`. Events SHALL be sorted by `occurred_at` ascending.

If the trade does not exist, the endpoint SHALL return HTTP 404.

#### Scenario: History after multiple stop changes

- **GIVEN** a trade with 3 events: initial at 95, trailed_up to 97, moved_to_be to 100
- **WHEN** the operator calls `GET /journal/trades/{id}/stop-history`
- **THEN** the response SHALL contain `events` of length 3 ordered chronologically
- **AND** each event SHALL include all required fields

### Requirement: Risk-free badge in Open Positions

The frontend Open Positions table on `/journal` SHALL display a visually distinct **`🔒 BE`** badge next to the stop value for any open position where `is_risk_free` is true.

The badge SHALL use green coloring consistent with the existing positive-tone convention and SHALL be inline with the stop value (not in a separate column) to communicate that the marker qualifies that specific value.

#### Scenario: Badge appears for risk-free position

- **GIVEN** an open trade returned by the API with `is_risk_free=true` and `stop_price=100`
- **WHEN** the operator views `/journal`
- **THEN** the Stop column for that row SHALL render `$100.00` followed by a green `🔒 BE` badge

#### Scenario: No badge for non-risk-free position

- **GIVEN** an open trade with `is_risk_free=false` (`stop_price=95, entry_price=100`)
- **WHEN** the row renders
- **THEN** no risk-free badge SHALL be visible

### Requirement: Stop history section in EditTradeModal

The frontend `EditTradeModal` SHALL render a read-only "Historial de stop" section that fetches and displays the trade's stop events.

The section SHALL appear below the existing "Snapshots del sistema al entry" block and SHALL show a small table with columns: timestamp, kind, `old → new`. If there are no events, a placeholder message `"sin cambios registrados"` SHALL be displayed.

The fetch SHALL happen via `GET /journal/trades/{id}/stop-history` on modal mount. Errors SHALL be logged but SHALL NOT prevent the modal from rendering other content.

#### Scenario: History section renders events

- **GIVEN** the operator opens EditModal for a trade with 2 stop events
- **WHEN** the modal mounts
- **THEN** the "Historial de stop" section SHALL show a 2-row table with timestamps, kinds, and old→new transitions

#### Scenario: History section handles empty state

- **GIVEN** the operator opens EditModal for a trade with no stop events (historical CSV import)
- **WHEN** the modal mounts
- **THEN** the section SHALL display `"sin cambios registrados"` instead of an empty table

**Implementation**: backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py); model [backend/app/models/stock.py](../../../backend/app/models/stock.py); migration `add_journal_stop_history.py`; frontend [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) and [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx).
