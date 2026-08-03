## ADDED Requirements

### Requirement: Market health classifies daily deterioration severity

The system SHALL classify every health-series session as `clean`, `mild`, or `severe` using the worst participation/leadership descriptor present, while retaining `damaged=true` for both mild and severe sessions.

#### Scenario: Mild pullback classification

- **WHEN** participation is `NARROWING` or leadership is `THINNING` and neither dimension has a severe descriptor
- **THEN** the day SHALL have `severity="mild"` and `damaged=true`

#### Scenario: Severe relapse classification

- **WHEN** participation is `COLLAPSING` or leadership is `COLLAPSING/EXHAUSTED`
- **THEN** the day SHALL have `severity="severe"` and `damaged=true`

#### Scenario: Constructive day classification

- **WHEN** participation is `STABLE/EXPANDING` and leadership is `HEALTHY/EXPANDING`
- **THEN** the day SHALL have `severity="clean"` and `damaged=false`

### Requirement: Recovery tolerates ordinary pullbacks

The system SHALL classify a non-ROBUST health window as `RECOVERING` when at least five of the latest seven classified sessions are clean and none of the latest three classified sessions is severe.

#### Scenario: Five clean sessions with mild interruptions qualifies

- **WHEN** the latest seven severities are `clean, clean, mild, clean, clean, mild, clean`
- **THEN** health SHALL be `RECOVERING`
- **AND** the mild sessions SHALL NOT reset all repair progress

#### Scenario: Recent severe deterioration blocks recovery

- **WHEN** at least five of the latest seven sessions are clean but any of the latest three sessions is severe
- **THEN** health SHALL NOT be `RECOVERING`

#### Scenario: Insufficient constructive participation does not qualify

- **WHEN** fewer than five of the latest seven sessions are clean
- **THEN** health SHALL retain the applicable `DAMAGED` or `FRAGILE` state

### Requirement: Severe deterioration prevents a robust label

The system SHALL NOT return `ROBUST` while any of the latest three classified sessions is severe, even when total damaged days and episodes are within the historical robust boundary.

#### Scenario: Fresh collapse after a clean window

- **WHEN** a 20-session window contains only one damaged session but that session is severe and lies within the latest three
- **THEN** health SHALL be `FRAGILE` or `DAMAGED` according to the remaining thresholds
- **AND** health SHALL NOT be `ROBUST` or `RECOVERING`

### Requirement: Health API exposes repair qualification inputs

The Market Context API SHALL preserve existing health fields and add rolling repair/severity diagnostics.

#### Scenario: Health response includes additive diagnostics

- **WHEN** `/api/v1/market-context/current` returns a health block
- **THEN** it SHALL include `repair_clean_days`, `repair_window_days`, `repair_required_clean_days`, `recent_severe_days`, and `severe_lookback_days`
- **AND** every `series` item SHALL include `severity` while retaining `damaged`
