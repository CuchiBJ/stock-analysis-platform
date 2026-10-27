## ADDED Requirements

### Requirement: Benchmark temporal evidence
The dedicated page SHALL show independent price and indicator dates relative to context.as_of. Earlier, later, invalid or absent dates and missing/nonfinite prices MUST NOT be presented as current. Earlier prices SHALL retain readable values with reduced prominence and neutral change color plus a textual warning.

#### Scenario: Stale QQQ with current SPY
- **WHEN** context and SPY are dated 2026-10-21 and QQQ is dated 2026-08-17
- **THEN** QQQ displays Dato atrasado, its exact date, reduced price prominence and neutral variation; SPY retains normal prominence
- **AND** the page says the benchmarks are not comparable for the context session

#### Scenario: Independent indicator date
- **WHEN** the price matches as_of but indicators are older or missing
- **THEN** the quote remains current while the indicators explicitly show their own stale or unavailable state

#### Scenario: Valid aligned quotes
- **WHEN** both finite prices have valid dates equal to as_of
- **THEN** the page shows no temporal comparison warning

#### Scenario: Unusable or future evidence
- **WHEN** a quote is missing, nonfinite, has an invalid date or a date after as_of
- **THEN** it is not labeled current and the comparison warning remains visible without invented values

### Requirement: Independent VIX age and refresh health
The API SHALL add refresh_failed to non-null VIX quotes while preserving status semantics. The page SHALL distinguish a prior dated close from a failed refresh without claiming live data or assuming an exchange calendar.

#### Scenario: Successfully fetched previous close
- **WHEN** refresh_failed is false and the VIX date precedes as_of
- **THEN** the page shows Cierre anterior al contexto and its date with reduced numeric prominence, without a refresh failure warning

#### Scenario: Cached quote after refresh failure
- **WHEN** refresh_failed is true, even with a quote dated as_of
- **THEN** the last quote remains dated and a refresh failure warning is visible

#### Scenario: Older API response
- **WHEN** refresh_failed is absent and status is stale
- **THEN** the page conservatively says Actualización no confirmada

#### Scenario: No quote or query failure
- **WHEN** VIX is null or the query fails
- **THEN** the existing unavailable or error state remains explicit and no zero quote is fabricated

### Requirement: Preserve operational behavior
The implementation SHALL preserve Dashboard bar/drawer, market policy, authentication, and unrelated market context sections.

#### Scenario: Freshness presentation changes
- **WHEN** a quote is classified as stale
- **THEN** market posture and its inputs remain unchanged and no ingestion or backfill is triggered
