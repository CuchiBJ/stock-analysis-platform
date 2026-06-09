## ADDED Requirements

### Requirement: Decision-level grouping via parent_trade_id

`JournalTrade` SHALL gain a self-referential nullable column `parent_trade_id: int | null` that links execution legs of the same operational decision into a single conceptual unit.

The convention SHALL be:

- `parent_trade_id IS NULL` means this row is the representative of its decision (the canonical leg the others link to).
- `parent_trade_id IS NOT NULL` means this row is a child execution belonging to the decision whose representative has `id = parent_trade_id`.
- The effective `decision_id` of any row SHALL be computed as `COALESCE(parent_trade_id, id)`.

#### Scenario: New manually-created trade is its own decision

- **GIVEN** the operator submits `POST /api/v1/journal/trades`
- **WHEN** the response returns
- **THEN** `parent_trade_id` SHALL be `null`
- **AND** `decision_id` SHALL equal `id`

#### Scenario: Partial close creates a linked child

- **GIVEN** an open trade with `id=42, qty=10, parent_trade_id=null`
- **WHEN** the operator partial-closes with `qty=3`
- **THEN** the new `closed` row SHALL have `parent_trade_id = 42`
- **AND** the original `id=42` row SHALL retain `parent_trade_id=null` (still the representative)
- **AND** both rows SHALL share the same `decision_id = 42`

#### Scenario: Further partial close from a child still links to original parent

- **GIVEN** the configuration above (parent id=42, first child id=43 linking to 42), and the open remainder is further partial-closed
- **WHEN** the new closed child is created
- **THEN** its `parent_trade_id` SHALL be `42` (the original parent), NOT `43` (the previous child)
- **AND** all three rows SHALL share `decision_id = 42`

### Requirement: Importer FIFO matching links siblings

The CSV importer SHALL ensure that all rows generated from a single Compra (whether closed children or the leftover open remainder) share a common decision via `parent_trade_id`.

The classification SHALL follow:

- If the Compra had any leftover open qty at the end of the walk → the leftover open row SHALL be the representative (`parent_trade_id=null`). All closed children generated from that Compra SHALL have `parent_trade_id = open_remainder.id`.
- If the Compra was fully consumed by Ventas → the first closed child (chronologically by source_row of the Venta) SHALL be the representative (`parent_trade_id=null`). The other closed children SHALL have `parent_trade_id = first_closed_child.id`.

#### Scenario: Partial CSV import — open remainder is parent

- **GIVEN** a CSV with Compra 5 NBIS @ $210 and Venta 0.5 @ $263
- **WHEN** the importer processes both rows
- **THEN** one OPEN row (qty=4.5) and one CLOSED row (qty=0.5) SHALL be persisted
- **AND** the OPEN row SHALL have `parent_trade_id=null`
- **AND** the CLOSED row SHALL have `parent_trade_id = open_row.id`
- **AND** both rows SHALL share the same `decision_id`

#### Scenario: Fully resolved CSV import — first closed leg is parent

- **GIVEN** a CSV with Compra 17 BTU @ $28.90 and two Ventas (12 @ $34, then 5 @ $35.69)
- **WHEN** the importer processes
- **THEN** two CLOSED rows SHALL be persisted (no open remainder)
- **AND** the first closed row (from the earlier Venta) SHALL have `parent_trade_id=null`
- **AND** the second closed row SHALL have `parent_trade_id = first_closed.id`

### Requirement: Stats endpoint exposes decision-level aggregates

`GET /api/v1/journal/stats` SHALL include a new top-level section `decision_overall` with metrics aggregated at the decision level (not the row level).

The section SHALL contain:

- `n_decisions_total`: count of unique decisions (`COUNT(DISTINCT decision_id)`).
- `n_fully_resolved`: decisions where all legs have non-null `exit_date`.
- `n_partially_resolved`: decisions with at least one open leg AND at least one closed leg.
- `n_fully_open`: decisions where no legs are closed.
- `decision_wins`, `decision_losses`, `decision_breakeven`: classified ONLY among `fully_resolved` decisions, based on the SIGN of `SUM(pnl_dollars across legs)` for that decision.
- `decision_win_rate`: `decision_wins / (decision_wins + decision_losses)`, or `null` when denominator is zero.
- `decision_total_realized_pnl`: sum of `pnl_dollars` across all closed legs.
- `decision_total_r`: sum of qty-weighted R per decision (each decision's `sum(r * qty)/sum(qty)` over its closed legs with R defined), then summed across all decisions.

The pre-existing trade-level `overall`, `by_setup`, `by_setup_context`, etc. sections SHALL remain unchanged — the change is purely additive.

#### Scenario: Decision aggregate distinct from trade aggregate

- **GIVEN** historical trades where BTU was bought once and sold in 2 parcial Ventas (both winners)
- **WHEN** the operator calls `journal_stats`
- **THEN** `overall.wins` SHALL include both BTU legs as 2 winners
- **AND** `decision_overall.decision_wins` SHALL include BTU as 1 winner (the decision is classified by its net pnl)

#### Scenario: Partially resolved decision does not count toward decision WR

- **GIVEN** NBIS bought 1 @ $210, partial-sold 0.5 @ $263 (closed leg +$24), the other 0.5 still open
- **WHEN** stats is computed
- **THEN** the NBIS decision SHALL be classified as `partially_resolved`
- **AND** it SHALL NOT appear in `decision_wins`, `decision_losses`, or `decision_breakeven`
- **AND** its realized $24 SHALL still be summed into `decision_total_realized_pnl`

### Requirement: Trade response exposes decision_id

`_trade_to_dict` (used by all endpoints returning trade rows) SHALL include two new keys in every trade payload:

- `parent_trade_id`: raw value of the column.
- `decision_id`: derived `COALESCE(parent_trade_id, id)` — the canonical identifier of the decision this leg belongs to.

#### Scenario: Decision id derivation in response

- **GIVEN** a trade with `id=42, parent_trade_id=null`
- **WHEN** the trade is serialized
- **THEN** the response SHALL include `parent_trade_id: null, decision_id: 42`

- **GIVEN** a trade with `id=43, parent_trade_id=42`
- **WHEN** the trade is serialized
- **THEN** the response SHALL include `parent_trade_id: 42, decision_id: 42`

### Requirement: Historical backfill CLI for decision grouping

A CLI script `backend/scripts/backfill_journal_decisions.py` SHALL exist that:

- Groups all `journal_trades` rows by the tuple `(symbol, entry_date, entry_price)` — this tuple uniquely identifies which physical Compra the legs came from.
- For each group with more than 1 row, picks the representative row using the rule:
  - If any row in the group has `exit_date IS NULL` (open) → that row is the representative.
  - Otherwise → the row with the lowest `id` is the representative.
- Updates the non-representative rows so their `parent_trade_id` equals the representative's `id`.

The script SHALL support `--dry-run` (logs intent without committing) and SHALL print a summary of groups detected and rows updated.

#### Scenario: Backfill detects BTU group

- **GIVEN** the historical journal contains 2 closed BTU rows with same `(symbol, entry_date, entry_price)`
- **WHEN** the operator runs the backfill
- **THEN** the row with lower id SHALL keep `parent_trade_id=null`
- **AND** the row with higher id SHALL be updated to `parent_trade_id = lower_id`

#### Scenario: Backfill leaves single-leg decisions untouched

- **GIVEN** a historical trade that is the only leg of its decision (no siblings sharing the tuple)
- **WHEN** the backfill runs
- **THEN** that row's `parent_trade_id` SHALL remain `null` (it is its own representative by default)

### Requirement: Frontend headline shows Decisions card

The `/journal` page SHALL render a second metrics card titled "Decisiones" below (or beside) the existing trade-level headline. It SHALL display three values from `decision_overall`:

- `n_decisions_total` labeled "Decisiones"
- `decision_win_rate` labeled "Decision WR" (formatted as percentage; renders "—" when null)
- `decision_total_r` labeled "Total R weighted"

A small information icon or tooltip SHALL clarify that a decision is "a single buy and all its partial sells" so the operator understands why the numbers differ from the row-level headline.

#### Scenario: Decisions card visible alongside trade-level

- **WHEN** the operator opens `/journal` with closed trades present
- **THEN** the trade-level headline (Trades, Win rate, Expectancy, Avg R) SHALL remain visible
- **AND** a second card showing decision-level metrics SHALL be rendered

### Requirement: Closed trades table shows decision_id column

The collapsible "Trades cerrados" table on `/journal` SHALL include a small column labeled `Decision` showing each row's `decision_id`. This enables the operator to visually identify rows that belong to the same decision without restructuring the table.

#### Scenario: Sibling rows share decision_id

- **GIVEN** 2 closed legs of the same BTU decision (ids 53 and 60, with 60.parent=53)
- **WHEN** the operator expands the table
- **THEN** both rows SHALL display `Decision: 53`

**Implementation**: backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py); model [backend/app/models/stock.py](../../../backend/app/models/stock.py); importer [backend/app/services/journal_importer.py](../../../backend/app/services/journal_importer.py); CLI [backend/scripts/backfill_journal_decisions.py](../../../backend/scripts/backfill_journal_decisions.py); frontend [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) and [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx); migration `add_journal_decision_grouping.py`.
