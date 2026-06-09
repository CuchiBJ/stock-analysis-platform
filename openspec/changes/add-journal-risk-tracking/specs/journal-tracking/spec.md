## ADDED Requirements

### Requirement: Explicit risk and account balance capture

The `JournalTrade` model SHALL accept and persist two optional operator-supplied risk dimensions captured at entry. Both fields SHALL be nullable to preserve backward compatibility with historical CSV-imported trades.

- `planned_risk_dollars: float | null` — the dollar amount the operator **intended** to risk on the position. When set, it SHALL take precedence over stop-derived inference for any downstream computation of "risk exposure".
- `account_balance_at_entry: float | null` — the operator's account balance at the moment of entry. When set, it SHALL enable normalization of risk and outcomes to percentage-of-account.

#### Scenario: Create trade with explicit risk plan

- **GIVEN** the operator submits `POST /api/v1/journal/trades` with `{symbol: "TSLA", entry_date: "2026-06-10", entry_price: 200, qty: 5, stop_price: 195, planned_risk_dollars: 25, account_balance_at_entry: 5000, ...}`
- **WHEN** the endpoint processes the request
- **THEN** the persisted row SHALL have `planned_risk_dollars=25.0` and `account_balance_at_entry=5000.0`

#### Scenario: Create trade without risk plan (backward compatible)

- **GIVEN** the operator submits a trade payload without the new fields
- **WHEN** the endpoint processes
- **THEN** the persisted row SHALL have both `planned_risk_dollars=null` and `account_balance_at_entry=null`
- **AND** the trade creation SHALL succeed

#### Scenario: Negative or zero values rejected

- **GIVEN** a payload with `planned_risk_dollars: -10`
- **WHEN** validation runs
- **THEN** the response SHALL be HTTP 422 (Pydantic constraint `gt=0`)

### Requirement: Effective risk derivation

The trade response SHALL include two derived fields that are not persisted in the database. Both are computed on-demand by the response serializer.

- `effective_risk_dollars`:
  - Returns `planned_risk_dollars` when not null.
  - Otherwise, returns `(entry_price - stop_price) * qty` when stop_price is set and `entry_price > stop_price`.
  - Otherwise, returns `null`.
- `risk_pct_of_account`:
  - Returns `effective_risk_dollars / account_balance_at_entry` when both are not null and `account_balance_at_entry > 0`.
  - Otherwise, returns `null`.

This derivation order reflects the institutional convention: operator intent (`planned_risk_dollars`) is the source of truth when stated; the stop-derived value is a fallback for trades where intent was not captured.

#### Scenario: Effective risk prefers planned over inferred

- **GIVEN** a trade with `entry_price=100, stop_price=90, qty=10, planned_risk_dollars=50`
- **WHEN** the response is built
- **THEN** `effective_risk_dollars` SHALL be `50` (not `100`, which is the stop-derived value)

#### Scenario: Effective risk falls back to stop when planned absent

- **GIVEN** a trade with `entry_price=100, stop_price=95, qty=10, planned_risk_dollars=null`
- **WHEN** the response is built
- **THEN** `effective_risk_dollars` SHALL be `50` (computed from `(100-95)*10`)

#### Scenario: Effective risk null when neither available

- **GIVEN** a trade with `planned_risk_dollars=null` and `stop_price=null`
- **WHEN** the response is built
- **THEN** both `effective_risk_dollars` and `risk_pct_of_account` SHALL be `null`

#### Scenario: Risk pct null when balance absent

- **GIVEN** a trade with `effective_risk_dollars=20` but `account_balance_at_entry=null`
- **WHEN** the response is built
- **THEN** `risk_pct_of_account` SHALL be `null` (no fabricated %)

### Requirement: Risk evolution breakdown in stats

`GET /api/v1/journal/stats` SHALL include a `risk_evolution` field: an array of monthly buckets, each summarizing the cohort of trades whose `entry_date` falls in that calendar month (YYYY-MM). The array SHALL be sorted ascending by month.

Each bucket SHALL contain:

- `month`: string YYYY-MM
- `n`: count of trades in this month
- `avg_planned_risk_dollars`: mean of `effective_risk_dollars` across trades in the bucket where it is not null; null if no trade has it.
- `avg_risk_pct_of_account`: mean of `risk_pct_of_account` across trades in the bucket where it is not null; null if no trade has both `effective_risk_dollars` and `account_balance_at_entry`.
- `total_r`: sum of `r_multiple` (using the same derivation as elsewhere); null if no trade has R defined.
- `total_pnl`: sum of `pnl_dollars` (derived); 0.0 if empty.

This breakdown allows the operator to detect at a glance whether their R unit ($ per trade) was changing over time and whether their R-cumulative edge tracks (or diverges from) their dollar P&L.

#### Scenario: Evolution exposes R unit shrinkage

- **GIVEN** 5 historical trades in 2025-12 with average inferred risk $42, and 6 trades in 2026-05 with average $9
- **WHEN** `journal_stats` is called
- **THEN** `risk_evolution` SHALL include `[{month: "2025-12", avg_planned_risk_dollars: ~42, ...}, ..., {month: "2026-05", avg_planned_risk_dollars: ~9, ...}]`

#### Scenario: Months with no risk data show nulls cleanly

- **GIVEN** all trades in 2025-12 lack both stop_price and planned_risk_dollars
- **WHEN** the bucket is computed
- **THEN** `avg_planned_risk_dollars` SHALL be `null` for that month
- **AND** `total_r` SHALL still be computed when r_multiples exist (since R is invariant to dollar risk)

### Requirement: Account balance prefill via localStorage

The frontend `NewTradeModal` and `EditTradeModal` SHALL persist the most recent `account_balance_at_entry` value in browser localStorage under key `journal_account_balance`. When the modal opens, it SHALL pre-populate the field from localStorage if present.

This rule reflects the operational reality that account balance changes infrequently (weekly or monthly) but is needed on every trade entry — forcing the operator to type it every time creates friction that kills the capture.

#### Scenario: First trade saves balance for future trades

- **GIVEN** localStorage has no `journal_account_balance` key
- **WHEN** the operator creates a trade with `account_balance_at_entry: 5000`
- **THEN** the trade SHALL be persisted with the value
- **AND** `localStorage.journal_account_balance` SHALL be set to `"5000"`

#### Scenario: Subsequent trade prefills from localStorage

- **GIVEN** localStorage has `journal_account_balance: "5000"`
- **WHEN** the operator opens `NewTradeModal`
- **THEN** the account balance input SHALL show `5000` pre-populated
- **AND** the operator MAY edit it before submitting

### Requirement: Risk percentage UI thresholds

When the operator has filled both `planned_risk_dollars` (or stop allows inference) and `account_balance_at_entry` in `NewTradeModal` or `EditTradeModal`, the form SHALL display a live-computed `Risk %` preview with visual classification:

- `Risk % >= 1.5%`: amber badge with message "⚠ sobre-tamaño (>1.5%)" — institutional convention is 0.5-1% per trade; >1.5% is aggressive sizing.
- `Risk % < 0.1%`: gray badge with message "insignificante (<0.1%)" — risk so small the trade contributes negligibly to outcome regardless of R-multiple.
- `0.1% <= Risk % < 1.5%`: neutral coloring, no badge.

This is a behavioral guardrail, not an enforcement — the operator can still submit, but receives clear visual feedback on whether their sizing is institutionally proportional.

#### Scenario: Sub-threshold sizing gets gray badge

- **GIVEN** account balance $10000 and planned risk $5
- **WHEN** the operator views the modal
- **THEN** Risk % display SHALL show `0.05%` with the "insignificante" badge

#### Scenario: Over-threshold sizing gets amber warning

- **GIVEN** account balance $1000 and planned risk $20
- **WHEN** the operator views the modal
- **THEN** Risk % display SHALL show `2.00%` with the "sobre-tamaño" amber badge

### Requirement: R unit Trend Card collapsed by default

The `/journal` page SHALL render an `R unit Trend Card` wrapped in an HTML `<details>` collapsible element, default closed, positioned below the Performance Matrix collapsible. When opened, it displays a table with one row per month containing: `month`, `n`, `avg planned risk $`, `avg risk %`, `total R`, `total $ P&L`.

The card is **not** part of the above-the-fold dashboard — it's retrospective analysis the operator opens deliberately, consistent with the existing pattern (closed trades, matrix).

#### Scenario: Card collapses by default

- **WHEN** the operator opens `/journal`
- **THEN** the R unit Trend Card content SHALL NOT be visible
- **AND** a summary line with the card's title SHALL be visible

#### Scenario: Coloring of monthly totals

- **GIVEN** a month with `total_r=+5.2` and `total_pnl=-$50`
- **WHEN** the card is expanded
- **THEN** the `total_r` cell SHALL render green
- **AND** the `total_pnl` cell SHALL render red

**Implementation**: backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py); model [backend/app/models/stock.py](../../../backend/app/models/stock.py); frontend [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx) and [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx); migration `add_journal_risk_tracking.py`.
