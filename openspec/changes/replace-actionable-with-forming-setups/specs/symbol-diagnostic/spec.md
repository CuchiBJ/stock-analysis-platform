## MODIFIED Requirements

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
- **THEN** the response `header` SHALL include `symbol`, `name`, `sector`, `industry`, `market_group`, `current_price`, and `group_strength` with `group`, `badge`, and `multiplier`

#### Scenario: Endpoint diagnoses each list

- **WHEN** the endpoint succeeds for a symbol with metrics
- **THEN** the response `lists` SHALL contain one object per system list: `forming`, `live`, `u_and_r`, `emerging_leaders`, `building_bases`, and `rs_leaders`
- **AND** each list object SHALL include `name`, `key`, `passes`, and `criteria`
- **AND** each criterion SHALL include `name`, `passes`, `actual`, and `threshold`

#### Scenario: Forming diagnostic agrees with production selection

- **GIVEN** a symbol that the production `/api/v1/transitions/forming` endpoint includes
- **WHEN** the diagnostic endpoint is called for the same metrics snapshot
- **THEN** `lists.forming.passes` SHALL be `true`
- **AND** its status SHALL be `eligible_ranked`

- **GIVEN** a symbol that passes formation eligibility but ranks below the endpoint cutoff
- **WHEN** the diagnostic endpoint is called
- **THEN** `lists.forming.passes` SHALL be `true`
- **AND** its status SHALL be `eligible_below_cutoff`
- **AND** the response SHALL include its rank and score gap to the cutoff

#### Scenario: Diagnostic explains promotion to Setup Feed

- **GIVEN** a structurally valid symbol is omitted from Setups Forming because it currently appears in the Setup Feed
- **WHEN** its diagnostic is requested
- **THEN** `lists.forming.status` SHALL equal `promoted_to_feed`
- **AND** the omission SHALL NOT be presented as a failed quality criterion

#### Scenario: Endpoint exposes transition history

- **WHEN** the endpoint succeeds
- **THEN** the response SHALL include `transition_history`, containing up to 10 transition observations from the last 30 days ordered by detection time descending
- **AND** each entry SHALL include transition type, detection date/time, and outcome status

#### Scenario: Endpoint exposes applied market context

- **WHEN** the endpoint succeeds
- **THEN** the response SHALL include `market_context_applied` with participation, leadership, regime, score contribution or multiplier, suppression state, and warnings used by current production surfaces

### Requirement: Symbol deep-dive page

The frontend SHALL provide a `/stock/[symbol]` page that consumes the diagnostic endpoint and renders the result.

#### Scenario: Page renders header with group badge

- **WHEN** the page loads for a valid symbol with metrics
- **THEN** the page SHALL render the symbol, current price, market group, and group-strength badge using the shared presentation

#### Scenario: Page shows status per list

- **WHEN** the page loads
- **THEN** each curated list SHALL render a clear state for pass/ranked, pass/below cutoff, promoted to feed, or failed eligibility
- **AND** each row SHALL be expandable to show criteria and rank evidence

#### Scenario: Criteria detail shows actual versus threshold

- **WHEN** the operator expands a list row
- **THEN** each criterion SHALL display its name, actual value, threshold, and pass/fail state
- **AND** failed criteria SHALL be visually distinguished from passing criteria

#### Scenario: Formation detail separates maturity from signal freshness

- **WHEN** the operator expands Setups Forming detail
- **THEN** the page MAY show structural age as maturity context
- **AND** it SHALL NOT label structural age as freshness of an executable signal

#### Scenario: Page handles 404 and no-metrics states

- **GIVEN** the endpoint returns 404
- **WHEN** the page loads
- **THEN** the page SHALL render `Symbol {ticker} not found`

- **GIVEN** the endpoint returns 200 with `header.has_metrics=false`
- **WHEN** the page loads
- **THEN** the page SHALL display header information plus a banner explaining the data gap

#### Scenario: Page renders transition history

- **WHEN** the page loads with non-empty `transition_history`
- **THEN** it SHALL render recent transitions with detection time, type, and outcome status

## REMOVED Requirements

### Requirement: Diagnostics SHALL reflect queue-specific 52-week-high eligibility

**Reason**: Its actionable-specific distinction is superseded by Setups Forming diagnostics. Live and breakout near-high rules remain governed by their existing production/spec contracts.

**Migration**: Remove actionable-specific criteria and score breakdown; add formation eligibility, rank, and promotion-state detail.
