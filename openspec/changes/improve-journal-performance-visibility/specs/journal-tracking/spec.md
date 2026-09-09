## ADDED Requirements

### Requirement: Canonical decision outcome drives filtering

The backend SHALL classify a decision as `win`, `loss`, or `breakeven` only when all legs are closed, using the existing break-even rule. Trade payloads SHALL expose `decision_outcome` and the current long-only `direction`.

When a trade or quantity-weighted decision R is available, any result inside the inclusive `±0.10R` band SHALL be classified as `breakeven` before evaluating signed dollar P&L. This prevents commissions from turning a displayed `+0.0xR` or `-0.0xR` scratch into a win or loss. The existing dollar break-even band SHALL remain the fallback when R is unavailable and SHALL continue to apply outside this R-specific override.

The Journal SHALL render clickable `Todos`, `Ganados`, `Pérdidas`, and `Break even` counters. Selecting a category SHALL immediately open and filter the operation list; `Todos` SHALL restore every decision with at least one realized exit.

#### Scenario: Operator filters winning decisions

- **GIVEN** two winning, one losing and one break-even decision
- **WHEN** the operator selects `Ganados · 2`
- **THEN** the list SHALL open with exactly the two winners
- **AND** `Todos` SHALL clear the filter.

**Implementation**: `backend/app/api/v1/endpoints/journal.py`; `frontend/app/journal/page.tsx`.

### Requirement: DCA holdings stay outside the trading scorecard

Trades whose canonical setup is `dca` SHALL be excluded from all Journal performance populations, including decision counts, win rate, P&L/R totals, winner/loser economics, evolution series, setup/context matrices, provenance coverage, and open-position counts. DCA rows SHALL remain persisted and available through the trade API/export; exclusion SHALL NOT delete or rewrite the holding.

The open-positions panel SHALL omit DCA holdings because they are accumulation positions without an expected Journal close. A separate `Posiciones DCA` panel SHALL keep those holdings visible, grouped by symbol with quantity-weighted average purchase price, total quantity, invested capital, and expandable purchase-level detail. The DCA panel SHALL offer edit/delete actions but SHALL NOT offer a close action.

#### Scenario: Open DCA purchases do not affect Journal

- **GIVEN** two open SPY purchases with setup `dca`
- **WHEN** Journal metrics and the open-position panel are rendered
- **THEN** neither purchase SHALL increment decisions, open positions, P&L, R, or other performance metrics
- **AND** neither SHALL appear in the open-position panel.
- **AND** a separate DCA panel SHALL show one aggregated SPY holding with both purchases available in its detail.

### Requirement: Repeated buys form one open position

Manual and imported buys in the same symbol whose holding intervals overlap SHALL share one decision. Repeated DCA buys SHALL group with other DCA buys, while DCA and tactical trades in the same symbol SHALL remain separate populations.

The open-position panel SHALL render one row per non-DCA symbol, using quantity-weighted average entry, total quantity and aggregate known risk. When the position contains multiple buys, the row SHALL identify the number of purchases and allow expanding them for individual close/edit/delete actions.

#### Scenario: Operator adds to an existing tactical position

- **GIVEN** an open tactical position in a symbol
- **WHEN** the operator records another buy in the same symbol
- **THEN** the backend SHALL link both rows to one decision
- **AND** the open-position panel SHALL show one aggregate row with both purchases available in its detail.

**Implementation**: `backend/app/services/journal_decisions.py`; `backend/app/api/v1/endpoints/journal.py`; `frontend/app/journal/page.tsx`.

#### Scenario: Near-zero R overrides a small dollar loss

- **GIVEN** a fully closed decision with `-0.02R` and negative P&L after commissions
- **WHEN** Journal outcomes are calculated
- **THEN** the decision SHALL be `breakeven`
- **AND** it SHALL be excluded from win/loss counters and their economic totals.

#### Scenario: Result outside the R band preserves current classification

- **GIVEN** a fully closed decision with an absolute R greater than `0.10R`
- **WHEN** Journal outcomes are calculated
- **THEN** the existing P&L and partial-exit classification rules SHALL continue to apply.

### Requirement: Economic outcome remains primary when the runner exits at entry

A fully resolved decision with positive total P&L, at least one profitable partial exit, and a remainder closed exactly at its stored entry price SHALL remain a `win` in counters, filters, economic metrics, and win-rate evolution. The API SHALL expose `runner_breakeven` as secondary result context and mark the matching execution with `is_runner_breakeven_exit`; neither field SHALL replace the canonical `win` outcome.

Runner detection SHALL use persisted entry/exit prices and decision linkage. It SHALL require exact price equality, without a new tolerance. A runner is unambiguous when it is the unique latest dated exit, or when it is the representative remainder with an explicitly linked `partial_take` child. Same-day historical executions without either signal SHALL remain untagged because the source stores dates but not times.

#### Scenario: Profitable partial followed by an entry-price runner

- **GIVEN** a decision with a profitable partial exit and positive total P&L/R
- **AND** its identifiable runner later closes exactly at its entry price
- **WHEN** Journal metrics and UI are rendered
- **THEN** the decision SHALL count as `win`, never as `breakeven`
- **AND** the closed-operation row, expanded detail, and evolution tooltip SHALL show `Ganada parcial · runner BE` as secondary context.

#### Scenario: Source data cannot identify a same-day runner

- **GIVEN** multiple exits on the same date, no execution times, and no explicit `partial_take` linkage
- **WHEN** the decision is rendered
- **THEN** its existing canonical classification SHALL remain unchanged
- **AND** the UI SHALL NOT invent a runner label.

**Implementation**: `backend/app/api/v1/endpoints/journal.py`; `frontend/app/journal/page.tsx`; `frontend/components/charts/WinRateEvolutionChart.tsx`.

### Requirement: Evolution points identify real trades

Each win-rate evolution point SHALL expose and display its real trade/decision id, symbol, long direction, entry date, final exit date, signed P&L, outcome and execution ids. Activating the tooltip item SHALL open that decision's expanded detail in the existing list.

The UI SHALL show date precision and SHALL NOT invent an execution time while `JournalTrade` stores `Date`. If the source later provides datetime precision, the tooltip SHOULD display it.

#### Scenario: Operator inspects a point

- **WHEN** the operator hovers a point associated with trade #53
- **THEN** the tooltip SHALL identify its symbol and real `#53` id instead of only its sequence number
- **AND** activating it SHALL open decision #53 in the list.

**Implementation**: `backend/app/api/v1/endpoints/journal.py` (`win_rate_evolution`); `frontend/components/charts/WinRateEvolutionChart.tsx`.

### Requirement: Winner and loser economics remain separate

`GET /api/v1/journal/stats` SHALL expose signed `decision_average_gain`, `decision_average_loss`, `decision_total_gains`, and `decision_total_losses`. Break-even, partial and open decisions SHALL be excluded. The Journal SHALL display all four values.

#### Scenario: Economic split excludes break even

- **GIVEN** outcomes +$40, +$60, -$10, -$30 and a break-even +$0.50
- **WHEN** stats are calculated
- **THEN** average/total gain SHALL be +$50/+$100
- **AND** average/total loss SHALL be -$20/-$40.

**Implementation**: `backend/app/api/v1/endpoints/journal.py`; `frontend/app/journal/page.tsx`.
