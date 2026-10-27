## ADDED Requirements

### Requirement: Dedicated twenty-session history preserves evidence
The overview response SHALL add up to20 ordered dated evolution rows with breadth_ratio and leader_count, using existing grouped dimension definitions. Zero coverage SHALL yield null metrics, while real zero observations remain zero. Current endpoint and Dashboard history MUST remain unchanged.

#### Scenario: Missing universe
- **WHEN** a dated dimension row has zero universe and leader_count zero
- **THEN** evolution contains null breadth_ratio and null leader_count for that date

#### Scenario: Genuine zero
- **WHEN** universe is positive and breadth_ratio and leader_count are zero
- **THEN** both zero observations are preserved

#### Scenario: Bounded historical read
- **WHEN** overview builds evolution
- **THEN** it requests20 sessions at or before context.as_of, without per-session queries or writes
- **AND** the legacy current response keeps its previous contract

### Requirement: Aligned readable evolution
The page SHALL display aligned breadth-percent, leader-count and severity histories before constituent details. Each series MUST expose its units, scale and coverage. Missing or invalid values MUST NOT be interpolated, forward-filled or rendered as zero.

#### Scenario: Missing middle observation
- **WHEN** the shared axis has three dates and breadth is missing on the second
- **THEN** no breadth line connects first to third and the second session reads Sin datos

#### Scenario: Unequal histories
- **WHEN** evolution has20 dates but severity has only12 matching dates
- **THEN** severity coverage is12/20 and absent dates show unknown, not clean

#### Scenario: Invalid or conflicting data
- **WHEN** dates are malformed or future, or duplicate dates have conflicting metric values
- **THEN** invalid/future dates are excluded and conflicting values become missing without inventing observations

#### Scenario: Sparse or legacy response
- **WHEN** evolution is missing or empty
- **THEN** the page shows Evolución no disponible without substituting legacy histories
- **WHEN** fewer than20 sessions exist
- **THEN** the actual session count and range are visible

### Requirement: Accessible session inspection
Users SHALL inspect exact values for any available session using a labeled keyboard-accessible selector. Default selection SHALL be the latest available date; selected markers SHALL align across plots. Selection MUST NOT affect policy or invoke requests.

#### Scenario: Select older session
- **WHEN** user selects an older available date
- **THEN** displayed date, breadth percentage, leader count, damage label and chart markers update together

#### Scenario: Refreshed response drops selected date
- **WHEN** selected date no longer exists after data refresh
- **THEN** the latest available date is selected safely

#### Scenario: Unavailable severity
- **WHEN** selected session has no explicit recognized severity
- **THEN** text and strip distinguish Sin datos from Sin daño clasificado
