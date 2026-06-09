## MODIFIED Requirements

### Requirement: Journal dashboard headline metrics

The `/journal` page SHALL render exactly three headline metric cards: **Trades**, **Expectancy**, and **Avg R**. These three are the minimum set that drives operational decisions (Trades = activity volume, Expectancy = decision quality in dollars, Avg R = decision quality in risk units).

The dashboard SHALL NOT render headline cards for: Win rate, Profit factor, Total P&L, or Avg duration. These metrics remain available in the stats API response and in drill-in views but SHALL NOT receive top-level visual weight.

#### Scenario: Operator views /journal headline

- **WHEN** the operator opens `/journal` with closed trades present
- **THEN** the headline section SHALL contain exactly 3 cards
- **AND** the labels SHALL be exactly "Trades", "Expectancy", "Avg R"

#### Scenario: Drill-in metrics remain accessible

- **WHEN** the operator opens a specific trade's edit view (or the API consumer reads `/journal/stats`)
- **THEN** Profit factor, Win rate, Total P&L, and Avg duration SHALL still be available in the response payload

### Requirement: Closed trades table is collapsible

The full closed trades table on `/journal` SHALL be wrapped in an HTML `<details>` element with `<summary>Trades cerrados (N) ▸</summary>` and SHALL be collapsed by default. The operator opens it explicitly when they need to scan the list.

This rule prevents the long table from anchoring visual attention and reduces scroll-driven noise on the dashboard.

#### Scenario: Default state collapsed

- **WHEN** the operator opens `/journal`
- **THEN** the closed trades table SHALL NOT be visible in the initial render
- **AND** a summary line "Trades cerrados (N) ▸" SHALL be visible with the count of closed trades

#### Scenario: Operator expands the table

- **WHEN** the operator clicks the summary
- **THEN** the full table SHALL render with all columns

### Requirement: Per-Context stand-alone breakdown removed

The dashboard SHALL NOT render a stand-alone "Por Contexto" breakdown card. The Performance Matrix (`Setup × regime_at_entry`, defined in `add-journal-system-snapshots`) is the single canonical view that integrates context dimension.

The stats API response MAY still include a `by_context` array for backward compatibility with API consumers, but the frontend SHALL ignore it.

#### Scenario: Dashboard does not render Por Contexto card

- **WHEN** the operator opens `/journal`
- **THEN** no card titled "Por Contexto" SHALL be rendered

## REMOVED Requirements

### Requirement: Persist derived computation fields

**Reason**: `cost_total`, `pnl_pct`, and `duration_days` are deterministic derivations from (`entry_price`, `qty`, `exit_price`, `entry_date`, `exit_date`). Persisting them creates two sources of truth (raw vs derived) and forces every mutation path (create / close / patch) to maintain consistency. They are computed on-demand in `_trade_to_dict` from the underlying fields. Historical trades retain their persisted values (no DB column drop in this change) for backward compatibility.

**Migration**: New trades created via `POST /journal/trades` or via `POST /trades/{id}/close` SHALL leave the columns `cost_total`, `pnl_pct`, `duration_days` as `NULL`. The `_trade_to_dict` serializer SHALL compute them on the fly when null:

- `cost_total = entry_price * qty` when both are present
- `pnl_pct = exit_price / entry_price - 1.0` when both are present
- `duration_days = (exit_date - entry_date).days` when both are present

API consumers see no change — the response shape remains stable.

### Requirement: Post-venta field in trade creation form

**Reason**: `post_venta` (what happened after exit) is a low-signal qualitative field that requires the operator to revisit the trade days after the fact. The audit determined it adds friction in `NewTradeModal` (it's never filled at trade creation) and only marginally in `CloseTradeModal` (the operator has not yet had time to observe post-exit behavior).

**Migration**: The field SHALL be removed from `NewTradeModal`. It remains visible and editable in `EditTradeModal` so the operator can return and fill it later if they want. The DB column SHALL NOT be dropped — existing 39 values stay accessible. The field SHALL be re-evaluated for full removal in 6 months based on usage telemetry.

### Requirement: Error note required at close

**Reason**: `add-journal-decision-provenance` introduces `exit_reason` as a categorized field that replaces the operational role `error_note` was playing. Forcing operators to type a free-text note on every close adds friction without adding categorization-quality data.

**Migration**: The `required` constraint on `error_note` in `CloseTradeModal` SHALL be removed. The field remains optional with a placeholder indicating it's for nuance / context, not for primary categorization (which `exit_reason` handles).

**Implementation**: frontend [frontend/app/journal/page.tsx](../../../frontend/app/journal/page.tsx) and [frontend/app/journal/TradeForms.tsx](../../../frontend/app/journal/TradeForms.tsx); backend [backend/app/api/v1/endpoints/journal.py](../../../backend/app/api/v1/endpoints/journal.py) (`create_open_trade`, `close_trade`, `patch_trade`, `_compute_outcomes`, `_trade_to_dict`); model docstrings in [backend/app/models/stock.py](../../../backend/app/models/stock.py).
