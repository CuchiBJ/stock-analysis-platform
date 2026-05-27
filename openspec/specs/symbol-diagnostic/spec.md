# symbol-diagnostic Specification

## Purpose
TBD - created by archiving change symbol-diagnostic. Update Purpose after archive.
## Requirements
### Requirement: Symbol diagnostic endpoint

The API SHALL expose `GET /api/v1/stocks/{symbol}/diagnostic` that returns a single object explaining why the symbol does or does not appear in each of the system's curated lists.

#### Scenario: Endpoint returns 404 for unknown ticker

- **GIVEN** the symbol is not present in the `stocks` table
- **WHEN** a client calls the endpoint
- **THEN** the response SHALL be HTTP 404 with detail `"Symbol {symbol} not found"`

#### Scenario: Endpoint handles symbols without metrics

- **GIVEN** the symbol exists in `stocks` but has no row in `stock_metrics` for the latest metrics date
- **WHEN** a client calls the endpoint
- **THEN** the response SHALL be HTTP 200 with `header.has_metrics=false` and `lists=[]`
- **AND** the response SHALL include a `note` field explaining the data gap

#### Scenario: Endpoint reports header info

- **WHEN** the endpoint succeeds
- **THEN** the response `header` SHALL include `symbol`, `name`, `sector`, `industry`, `market_group`, `current_price`, and `group_strength` (with `group`, `badge`, `multiplier`)

#### Scenario: Endpoint diagnoses each list

- **WHEN** the endpoint succeeds for a symbol with metrics
- **THEN** the response `lists` SHALL contain one object per system list: `actionable`, `live`, `u_and_r`, `emerging_leaders`, `building_bases`
- **AND** each list object SHALL include `name` (human-readable), `key` (machine ID), `passes` (bool), and `criteria` (array)
- **AND** each criterion SHALL include `name`, `passes` (bool), `actual` (value or null), `threshold` (value, range, or string)

#### Scenario: Diagnostic agrees with production filter

- **GIVEN** a symbol that the production `/api/v1/transitions/actionable` endpoint includes in its results
- **WHEN** the diagnostic endpoint is called for the same symbol
- **THEN** `lists.actionable.passes` SHALL be `true`

- **GIVEN** a symbol that the production endpoint excludes
- **WHEN** the diagnostic endpoint is called
- **THEN** `lists.actionable.passes` SHALL be `false`
- **AND** at least one criterion in `lists.actionable.criteria` SHALL have `passes=false`

#### Scenario: Endpoint exposes transition history

- **WHEN** the endpoint succeeds
- **THEN** the response SHALL include `transition_history`: an array of up to 10 `transition_observations` for the symbol from the last 30 days, ordered by `date_detected` descending
- **AND** each entry SHALL include `transition_type`, `date_detected`, and `outcome_status`

#### Scenario: Endpoint exposes applied market context

- **WHEN** the endpoint succeeds
- **THEN** the response SHALL include `market_context_applied` with `participation`, `leadership`, and `score_multiplier` (the same multiplier that would apply if the symbol entered `/actionable`)

### Requirement: Symbol deep-dive page

The frontend SHALL provide a `/stock/[symbol]` page that consumes the diagnostic endpoint and renders the result.

#### Scenario: Page renders header with group badge

- **WHEN** the page loads for a valid symbol with metrics
- **THEN** the page SHALL render the symbol, current price, market group, and group-strength badge (using the same `GroupStrengthBadge` component as the other surfaces)

#### Scenario: Page shows pass/fail per list

- **WHEN** the page loads
- **THEN** for each of the 5 lists, the page SHALL render a row with the list name and a clear pass (green check) or fail (red cross) indicator
- **AND** each row SHALL be expandable to show the criteria detail

#### Scenario: Criteria detail shows actual vs threshold

- **WHEN** the operator expands a list row
- **THEN** each criterion SHALL display its name, the actual value, the threshold, and a pass/fail indicator
- **AND** failed criteria SHALL be visually distinguished from passing ones

#### Scenario: Page handles 404 and no-metrics states

- **GIVEN** the endpoint returns 404
- **WHEN** the page loads
- **THEN** the page SHALL render an error state "Symbol {ticker} not found"

- **GIVEN** the endpoint returns 200 with `header.has_metrics=false`
- **WHEN** the page loads
- **THEN** the page SHALL display the header info plus a banner explaining the data gap

#### Scenario: Page renders transition history

- **WHEN** the page loads with `transition_history` non-empty
- **THEN** the page SHALL render the list of recent transitions with date, type, and outcome status badge

### Requirement: Symbol search in dashboard layout

The frontend SHALL render a `SymbolSearch` input in the top navigation that lets the operator type any ticker and navigate to its deep-dive page.

#### Scenario: Pressing Enter navigates to deep-dive

- **WHEN** the operator types a ticker in the search input AND presses Enter
- **THEN** the frontend SHALL navigate to `/stock/{TICKER_UPPERCASE}`

#### Scenario: Empty input does nothing

- **WHEN** the operator presses Enter with an empty input
- **THEN** no navigation SHALL occur

