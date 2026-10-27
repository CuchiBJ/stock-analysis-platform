## ADDED Requirements

### Requirement: Dedicated context page SHALL preserve Dashboard behavior
The system SHALL provide an authenticated `/market-context` page with a `Market context` link immediately after Dashboard. It SHALL preserve the existing Dashboard context bar, drawer, data fetching and decision rules. The page SHALL organize the current posture, participation, leadership, health, follow-through and raw evidence with progressive disclosure, and prominently present SPY/QQQ and dated VIX.

#### Scenario: Existing Dashboard interaction
- **WHEN** an operator clicks the existing Dashboard context bar
- **THEN** the existing drawer opens unchanged, rather than navigating to the new page

#### Scenario: New page navigation
- **WHEN** an authenticated operator selects Market context
- **THEN** the dedicated page opens with current context and additional market evidence

### Requirement: Sector constituents SHALL reconcile with breadth totals
The page SHALL expose new 52-week highs and lows grouped by sector using existing quality filters and strict OHLC comparisons against the preceding 252 SPY sessions. Counts and constituents SHALL share one calculation and date. Missing sectors SHALL be explicit, ties SHALL not qualify, and dual extremes SHALL appear in both lists. Coverage, exclusions and empty/unavailable states SHALL be visible.

#### Scenario: Dual extreme and missing sector
- **WHEN** an eligible symbol without sector records both new extremes
- **THEN** it appears in both lists under Sin sector and contributes once to each event count

#### Scenario: Incomplete history
- **WHEN** a symbol lacks any required valid session
- **THEN** it is excluded from annual breadth and no invented constituent or zero-event interpretation is shown

### Requirement: Benchmark and volatility evidence SHALL be dated and informational
SPY and QQQ SHALL have prominent price, daily change and trend evidence without changing decision policy. Missing inputs SHALL remain unknown. Quotes SHALL use data no later than context date and disclose older price or metrics dates. VIX SHALL show the official Cboe daily close, previous-close changes, actual date and source independently from internal context loading.

#### Scenario: VIX unavailable
- **WHEN** the provider fails and no cached data exists
- **THEN** VIX is shown as unavailable while the internal market context remains usable

#### Scenario: Historical or stale evidence
- **WHEN** the context date precedes a downloaded quote or the available quote precedes context
- **THEN** no future quote is used and older evidence is visibly dated

### Requirement: New endpoints and page SHALL retain authentication and resilience
The additive endpoints SHALL inherit protected-request authorization. Frontend requests SHALL use the shared API client and support loading, empty, retryable errors, partial availability and session loss without showing retained private data after logout.

#### Scenario: Unauthorized request
- **WHEN** an unauthenticated caller requests either new endpoint
- **THEN** access is rejected by existing authentication dependencies

#### Scenario: Refresh fails
- **WHEN** an authenticated page refresh fails
- **THEN** the failure and retry action are visible and any retained data is clearly marked as not refreshed
