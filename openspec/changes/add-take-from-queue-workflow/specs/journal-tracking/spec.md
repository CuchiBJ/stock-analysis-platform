## ADDED Requirements

### Requirement: Trade draft endpoint produces queue-locked prefill

`GET /api/v1/journal/trade-draft?symbol=<X>&setup=<Y>` SHALL return a deterministic prefill object that the frontend can pass to `NewTradeModal` to create a queue-originated trade with minimal operator input. The endpoint SHALL NOT create or persist anything — it is read-only.

The response object SHALL include:

- `symbol` (echo of input)
- `setup` (echo of input, validated against `SETUP_OPTIONS`)
- `entry_price` (number) — the `close` value of the most recent `stock_metrics` row for the symbol
- `stop_price_suggested` (number) — the `ema21` value of the same row
- `from_queue: true` (locked at the endpoint level)
- `entry_reason: "queue_signal"` (locked)
- `regime_at_entry`, `system_score_at_entry`, `group_strength_at_entry`, `leader_health_at_entry` — preview snapshots computed via `take_entry_snapshot(symbol, today())` for display in the modal banner; these are NOT what gets persisted (the persisted snapshots come from the snapshot service running at save time)

#### Scenario: Draft for a symbol in the queue

- **GIVEN** symbol "NBIS" exists in `stocks` with a recent `stock_metrics` row (close=$210, ema21=$197)
- **WHEN** the operator calls `GET /journal/trade-draft?symbol=NBIS&setup=building_base`
- **THEN** the response SHALL include `entry_price=210` and `stop_price_suggested=197`
- **AND** SHALL include `from_queue=true`, `entry_reason="queue_signal"`
- **AND** SHALL include preview snapshots populated where the underlying engines have data

#### Scenario: Draft for a symbol without metrics

- **GIVEN** symbol "FOO" exists but has no `stock_metrics` rows
- **WHEN** the endpoint is called
- **THEN** the response SHALL be HTTP 404 with `detail: "no metrics for symbol"`

#### Scenario: Draft with invalid setup

- **GIVEN** a request with `setup=fake_setup` (not in `SETUP_OPTIONS`)
- **WHEN** the endpoint validates input
- **THEN** the response SHALL be HTTP 422

#### Scenario: Draft does not persist

- **GIVEN** the draft endpoint is called for a valid (symbol, setup)
- **WHEN** the response returns 200
- **THEN** `SELECT COUNT(*) FROM journal_trades WHERE symbol=...` SHALL be unchanged

### Requirement: NewTradeModal accepts prefill and locks queue-derived fields

The frontend `NewTradeModal` SHALL accept an optional `prefill` prop. When a non-null `prefill` is provided:

- The `symbol` and `setup` inputs SHALL be rendered read-only (not editable).
- The internal state SHALL set `from_queue=true` and `entry_reason="queue_signal"` automatically, without exposing those as user-facing dropdowns.
- The `entry_price` and `stop_price` inputs SHALL be pre-populated with the prefill values but SHALL remain editable (operator may adjust if their actual fill differs).
- A banner SHALL display the preview snapshots (e.g. "Tomando trade del queue · regime=expansive · system_score=0.74 · group=strong") so the operator sees what the system reads at the moment.

When `prefill` is absent (manual "Nuevo trade" button), the modal SHALL behave as in `add-journal-decision-provenance`: full editable form, `from_queue` defaults to `null`, `entry_reason` defaults to `discretionary` and is operator-editable.

#### Scenario: Operator takes a trade from the queue

- **GIVEN** the operator is on `/queue` viewing a Building Bases card for NBIS
- **WHEN** the operator clicks "Tomar trade"
- **THEN** the modal SHALL open with `symbol="NBIS"` and `setup="building_base"` locked
- **AND** the banner SHALL show the preview snapshot values
- **AND** the only fields requiring operator input SHALL be `qty` and optionally `entry_price` / `stop_price` adjustments

#### Scenario: Operator creates a trade manually

- **GIVEN** the operator clicks "Nuevo trade" on `/journal`
- **WHEN** the modal opens
- **THEN** `symbol` and `setup` SHALL be editable
- **AND** no preview banner SHALL be visible
- **AND** the submitted trade SHALL have `from_queue=null` (operator didn't mark anything)
- **AND** `entry_reason` SHALL default to `discretionary` and be operator-editable

### Requirement: Take from queue button in queue cards

Each setup card in `/queue` (across the three lenses: U&R, Emerging Leaders, Building Bases) SHALL render a "Tomar trade" button that, when clicked, fetches the trade draft for that (symbol, lens-setup) pair and opens `NewTradeModal` with the prefill.

The `setup` passed to the draft endpoint SHALL correspond to the lens of origin: `u_and_r`, `emerging`, or `building_base` respectively.

#### Scenario: Button in U&R card

- **GIVEN** the operator views the U&R queue with TSLA in the list
- **WHEN** the operator clicks "Tomar trade" on the TSLA card
- **THEN** the request SHALL be `GET /journal/trade-draft?symbol=TSLA&setup=u_and_r`
- **AND** the modal SHALL open prefilled

### Requirement: Take from queue button in stock detail

When a symbol's `/stock/[symbol]` diagnostic page reports that the symbol is active in at least one lens, the page SHALL render a "Tomar trade" CTA.

- When the symbol is active in exactly one lens, clicking the CTA SHALL invoke the draft for that lens directly.
- When the symbol is active in multiple lenses, the CTA SHALL present a dropdown of active lenses; the operator picks one and the draft proceeds.
- When the symbol is in zero lenses, the CTA SHALL NOT be rendered.

This rule preserves the transparency that "off-system" trades go through the manual `NewTradeModal`, not through the queue workflow.

#### Scenario: Multi-lens active symbol

- **GIVEN** AAPL is active in both U&R and Building Bases
- **WHEN** the operator opens `/stock/AAPL`
- **THEN** a "Tomar trade" button with a dropdown showing both lenses SHALL be visible

#### Scenario: Symbol not in any lens

- **GIVEN** XYZ has metrics but is not in any active lens
- **WHEN** the operator opens `/stock/XYZ`
- **THEN** no "Tomar trade" CTA SHALL be rendered
- **AND** the operator SHALL access the journal via the manual "Nuevo trade" button only

### Requirement: Stats endpoint reports provenance capture rate

`GET /api/v1/journal/stats` SHALL include a `provenance_capture_rate` field defined as `count(from_queue IS NOT NULL) / count(total trades)`. This metric tells the operator (and the product owner) what fraction of trades have a tracked origin — the operational health signal of the take-from-queue workflow.

A `null` `from_queue` SHALL count as "not captured" (denominator only). A `true` or `false` SHALL count as "captured" (numerator).

#### Scenario: Capture rate before and after workflow adoption

- **GIVEN** the 34 historical trades all have `from_queue=null`
- **WHEN** the operator opens `/journal/stats`
- **THEN** `provenance_capture_rate` SHALL be `0.0`

- **GIVEN** the operator then captures 6 new trades via the workflow (all `from_queue=true`)
- **WHEN** the endpoint is called again
- **THEN** `provenance_capture_rate` SHALL be `6/40 = 0.15`

**Implementation**: backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) (new endpoint `/journal/trade-draft`); frontend [frontend/components/queue/TakeFromQueueButton.tsx](../../../frontend/components/queue/TakeFromQueueButton.tsx) (new); [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) (`NewTradeModal` prefill prop); integrations in queue card components and `frontend/app/stock/[symbol]/page.tsx`.
