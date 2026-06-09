## ADDED Requirements

### Requirement: Trade decision provenance fields

Every `JournalTrade` SHALL persist the origin of the entry decision and the reason for the exit, so the operator and the system can separate decisions taken inside the operating system (queue-driven) from decisions taken outside it (discretionary).

The journal SHALL store three new fields:

- `from_queue: boolean | null` — `true` when the trade was created via the take-from-queue workflow; `false` when explicitly marked as off-system; `null` when origin is unknown (default for historical and manually-created trades until the operator marks them).
- `entry_reason: string` — one of: `queue_signal`, `discretionary`, `continuation`, `news`, `other`. Default `other`.
- `exit_reason: string` — one of: `stop_hit`, `target`, `trail`, `thesis_broken`, `discretionary`, `partial_take`, `unknown`. Default `unknown`.

#### Scenario: Creating a trade persists entry_reason from payload

- **GIVEN** the operator submits `POST /api/v1/journal/trades` with `{symbol: "TSLA", entry_date: "2026-06-05", entry_price: 200, qty: 10, setup: "u_and_r", context: "favorable", entry_reason: "queue_signal", from_queue: true}`
- **WHEN** the endpoint processes the request
- **THEN** the persisted row SHALL have `entry_reason="queue_signal"` and `from_queue=true`

#### Scenario: Creating a trade without entry_reason uses default

- **GIVEN** the operator submits a trade payload without specifying `entry_reason`
- **WHEN** the endpoint processes the request
- **THEN** the persisted row SHALL have `entry_reason="other"` and `from_queue=null`

#### Scenario: Invalid entry_reason is rejected

- **GIVEN** a payload with `entry_reason="hunch"`
- **WHEN** the endpoint validates the input
- **THEN** the response SHALL be HTTP 422 with a clear validation error referencing the allowed values

### Requirement: Partial close auto-infers exit_reason

When the operator closes a fraction of an open position (i.e. `payload.qty < trade.qty`), the system SHALL pre-assign `exit_reason="partial_take"` to the newly-created closed child trade unless the operator explicitly provides a different value.

This rule reflects the operational reality that partial closes are almost always either profit-taking on a portion or risk reduction — both fall under the `partial_take` semantic — and removes a forced click in the high-frequency flow.

#### Scenario: Partial close without exit_reason gets partial_take

- **GIVEN** an open trade id=42 with `qty=10`
- **WHEN** the operator calls `POST /api/v1/journal/trades/42/close` with `{exit_date: "2026-06-05", exit_price: 220, qty: 3}` (no exit_reason)
- **THEN** the response `closed` object SHALL have `exit_reason="partial_take"`
- **AND** the response `remaining_open` object SHALL keep `exit_reason="unknown"`

#### Scenario: Partial close with explicit exit_reason overrides default

- **GIVEN** the same open trade
- **WHEN** the operator submits `{exit_date: "2026-06-05", exit_price: 220, qty: 3, exit_reason: "target"}`
- **THEN** the closed child SHALL have `exit_reason="target"`

#### Scenario: Full close requires exit_reason in payload

- **GIVEN** the operator submits a full close (no qty or qty equals trade.qty) without exit_reason
- **WHEN** the endpoint processes
- **THEN** the trade SHALL retain `exit_reason="unknown"` (the original default)
- **AND** the close SHALL succeed (exit_reason is optional in the payload — auto-infer only applies to partials)

### Requirement: Vocabulary endpoint exposes decision enums

`GET /api/v1/journal/vocab` SHALL include `entry_reason_options` and `exit_reason_options` arrays so the frontend can render dropdowns from a single source of truth.

#### Scenario: Vocab response includes new enums

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `entry_reason_options` exactly equal to `["queue_signal","discretionary","continuation","news","other"]`
- **AND** SHALL include `exit_reason_options` exactly equal to `["stop_hit","target","trail","thesis_broken","discretionary","partial_take","unknown"]`

### Requirement: Stats endpoint exposes discretionary vs systematic breakdown

`GET /api/v1/journal/stats` SHALL include two new top-level aggregations: `by_entry_reason` and `discretionary_vs_systematic`. This allows the operator to answer the core product question: is the queue-driven flow producing better outcomes than discretionary trades?

#### Scenario: Stats response includes by_entry_reason

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `by_entry_reason` as an array of `{entry_reason, n, win_rate, expectancy, profit_factor, avg_r, avg_duration_days, total_pnl, wins, losses, breakeven}` rows
- **AND** the array SHALL contain one entry per distinct `entry_reason` value present in closed trades

#### Scenario: Stats response includes discretionary vs systematic aggregate

- **WHEN** the endpoint is called
- **THEN** the response SHALL include `discretionary_vs_systematic` as an object with two keys: `systematic` (all closed trades where `entry_reason == "queue_signal"`) and `discretionary` (all other closed trades), each with the same aggregate shape used elsewhere

#### Scenario: Systematic bucket with no trades returns zeros honestly

- **GIVEN** no trades with `entry_reason="queue_signal"` exist (historical data only)
- **WHEN** the endpoint is called
- **THEN** `discretionary_vs_systematic.systematic` SHALL have `n=0` and `win_rate=null`, `expectancy=null`, `profit_factor=null` (no fabricated zeros)

### Requirement: Discretionary vs systematic widget enforces data starvation honesty

The `/journal` page SHALL display the "Discrecional vs Sistémico" widget above the Performance Matrix. When either bucket has `n < 5`, that bucket SHALL render an "insuficiente — n=X" badge in amber instead of computed metrics, and SHALL NOT render win-rate / expectancy with success/failure coloring.

This prevents the operator from acting on noise (e.g. a single +3R systematic trade producing a "100% win rate" headline).

#### Scenario: Both buckets insufficient — widget shows placeholders

- **GIVEN** systematic has 0 trades and discretionary has 3 trades
- **WHEN** the operator opens `/journal`
- **THEN** both columns SHALL show amber "insuficiente" badges with the actual N
- **AND** no expectancy/WR coloring SHALL appear

#### Scenario: One bucket sufficient — only the sufficient one shows colored metrics

- **GIVEN** systematic has 7 trades and discretionary has 28 trades
- **WHEN** the widget renders
- **THEN** both columns SHALL show full metrics with normal coloring (green/red on positive/negative)

**Implementation**: backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py); model [backend/app/models/stock.py](../../../backend/app/models/stock.py); frontend [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) and [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx); migration `add_journal_decision_provenance.py`.
