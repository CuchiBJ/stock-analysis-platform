## ADDED Requirements

### Requirement: Persist actual emitted market posture per session
The system SHALL durably retain the latest observed valid posture returned by current or overview, keyed by its context session with UTC observation time and complete posture payload. It SHALL NOT manufacture prior-session records via historical recomputation.

#### Scenario: Repeated and concurrent observations
- **WHEN** multiple observations occur for the same session
- **THEN** one record retains the latest timestamp and payload using atomic conflict handling and an older write cannot overwrite a newer observation

#### Scenario: Persistence failure
- **WHEN** the posture table is unavailable or a database write fails
- **THEN** the ordinary context response remains usable and overview posture_history reports unavailable without invented records

### Requirement: Expose exact dated posture evidence without changing current response
Overview SHALL expose additive posture_history with status and records for the exact current and previous SPY reference dates; current SHALL retain its existing response body. These routes SHALL remain authenticated.

#### Scenario: Missing earlier observation
- **WHEN** a current posture is recorded but the previous reference session was never observed
- **THEN** overview includes only actual records and no earlier date is substituted

### Requirement: Compare only valid observed posture pairs
The daily changes summary SHALL compare known postures only for its two exact reference dates with valid UTC timestamps and current-state agreement. Missing, duplicate, invalid or incompatible evidence SHALL produce an explicit unavailable result.

#### Scenario: Restrictiveness changes
- **WHEN** valid records move from NORMAL to DEFENSIVO
- **THEN** the row says Más restrictiva and shows both states, dates and recording times ahead of improvements

#### Scenario: Stable, less restrictive or legacy evidence
- **WHEN** a valid pair has identical states or a transition toward a more permissive state
- **THEN** it says Sin cambio or Menos restrictiva respectively with evidence
- **AND** a legacy response or incomplete pair says Sin comparación disponible rather than Sin cambio
