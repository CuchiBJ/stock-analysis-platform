## MODIFIED Requirements

### Requirement: Calibration endpoint by transition type

The system SHALL expose `GET /api/v1/calibration/by-transition-type` returning historical, recent, baseline, and current-regime empirical outcome cohorts for every non-STABLE `OperationalTransition` type. Cohorts SHALL be computed exclusively from attributes persisted at detection time and SHALL retain the legacy historical row fields for backward compatibility.

#### Scenario: All transition types appear in the response

- **WHEN** a client calls `GET /api/v1/calibration/by-transition-type`
- **THEN** the response SHALL contain one row per non-STABLE transition type regardless of whether observations exist

#### Scenario: Four cohorts are reported

- **WHEN** a transition has settled observations across multiple dates and regimes
- **THEN** its row SHALL contain `historical`, `recent`, `baseline`, and `current_regime` cohort objects
- **AND** `recent` SHALL include only signals detected in the 21 calendar days ending at the current as-of date, aligned with the current follow-through window
- **AND** `baseline` SHALL include only signals detected in the 180 calendar days immediately preceding the recent window
- **AND** `current_regime` SHALL include only signals whose persisted `regime_at_detection` equals the reported current regime

#### Scenario: Cohort rates and uncertainty are honest

- **WHEN** a cohort contains at least 20 settled outcomes
- **THEN** it SHALL expose win rate, delivery rate, and a 95% Wilson interval for delivery rate
- **AND** delivery rate SHALL equal `SUCCESS / (SUCCESS + FAILURE + NEUTRAL)`
- **WHEN** it contains fewer than 20 settled outcomes
- **THEN** rates and confidence interval SHALL be null and status SHALL be `insufficient` or `no_data`

#### Scenario: Pending counts remain visible

- **WHEN** a cohort contains `PENDING` or `INSUFFICIENT_DATA` observations
- **THEN** its pending count SHALL include both statuses
- **AND** pending observations SHALL NOT enter rate denominators

### Requirement: Calibration page

The frontend SHALL provide a `/calibration` page that distinguishes historical evidence from evidence comparable to the current environment and compresses it into an operational read.

#### Scenario: Current context is explicit

- **WHEN** the operator opens Calibration
- **THEN** the page SHALL display the current as-of date, regime, follow-through descriptor, recent delivery rate, baseline rate, and posture when available
- **AND** it SHALL explicitly state that calibration is evidence rather than a guarantee

#### Scenario: Cohort comparison is visible

- **WHEN** calibration rows are rendered
- **THEN** each row SHALL show historical delivered, recent delivered, current-regime delivered, recent settled sample size, and drift
- **AND** insufficient cohorts SHALL show their sample deficit rather than a percentage

#### Scenario: Drift requires statistical separation

- **WHEN** baseline and recent cohorts are empirical and their Wilson intervals do not overlap
- **THEN** drift SHALL be `improving` when recent delivery is higher and `deteriorating` when it is lower
- **WHEN** intervals overlap
- **THEN** drift SHALL be `stable`
- **WHEN** either the baseline or recent cohort is insufficient
- **THEN** drift SHALL be `insufficient`

### Requirement: Historical regime labels can be corrected

The system SHALL expose an admin reclassification operation that recomputes each observation's `regime_at_detection` from the market snapshot at or before its detection date.

#### Scenario: Existing labels are reclassified without lookahead

- **WHEN** regime reclassification is triggered
- **THEN** observations SHALL be grouped by detection date
- **AND** each group SHALL use `MarketRegimeEngine.detect_regime(date_detected)`
- **AND** the response SHALL report evaluated and changed counts by regime
- **AND** empirical probability caches SHALL be cleared

#### Scenario: Row ordering prioritizes operational risk

- **WHEN** rows are displayed
- **THEN** bullish transitions with deteriorating drift SHALL appear before stable, improving, and insufficient rows
