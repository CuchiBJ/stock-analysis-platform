# calibration-reporting Specification

## Purpose
TBD - created by archiving change calibration-feedback-loop. Update Purpose after archive.
## Requirements
### Requirement: Calibration endpoint by transition type

The system SHALL expose `GET /api/v1/calibration/by-transition-type` returning the observed empirical success rate per `OperationalTransition` type, computed from `transition_observations` rows whose `outcome_status` is resolved.

#### Scenario: All transition types appear in the response

- **GIVEN** the `OperationalTransition` enum defines N non-STABLE values
- **WHEN** a client calls `GET /api/v1/calibration/by-transition-type`
- **THEN** the response SHALL contain exactly N rows, one per non-STABLE value, regardless of whether observations exist for each type

#### Scenario: Resolved counts are tallied per type

- **GIVEN** `transition_observations` contains rows with `outcome_status IN ('SUCCESS', 'FAILURE', 'NEUTRAL', 'PENDING', 'INSUFFICIENT_DATA')`
- **WHEN** the endpoint is queried
- **THEN** for each transition type, `n_resolved` SHALL equal the count of rows where `outcome_status IN ('SUCCESS', 'FAILURE')`
- **AND** `success_count` SHALL equal the count where `outcome_status = 'SUCCESS'`
- **AND** `failure_count` SHALL equal the count where `outcome_status = 'FAILURE'`
- **AND** `n_pending` SHALL equal the count where `outcome_status IN ('PENDING', 'INSUFFICIENT_DATA')`

#### Scenario: Success rate exposed only when sample threshold met

- **GIVEN** a transition type with `n_resolved >= 5`
- **WHEN** the endpoint computes the row
- **THEN** `success_rate` SHALL equal `success_count / n_resolved` as a float in [0.0, 1.0]
- **AND** `status` SHALL equal `'empirical'`

- **GIVEN** a transition type with `0 < n_resolved < 5`
- **WHEN** the endpoint computes the row
- **THEN** `success_rate` SHALL be `null`
- **AND** `status` SHALL equal `'insufficient'`

- **GIVEN** a transition type with `n_resolved = 0`
- **WHEN** the endpoint computes the row
- **THEN** `success_rate` SHALL be `null`
- **AND** `status` SHALL equal `'no_data'`

#### Scenario: Minimum sample threshold exposed for client display

- **WHEN** the endpoint is queried
- **THEN** the response SHALL include `min_samples_required: 5` at the top level

#### Scenario: ETA for first calibration data when nothing resolved yet

- **GIVEN** `n_pending > 0` across all rows and no resolved observations exist
- **WHEN** the endpoint is queried
- **THEN** the response SHALL include `eta_first_data: <date>` computed as the oldest `date_detected` in pending status plus 10 days

- **GIVEN** at least one resolved observation exists OR no pending observations exist
- **WHEN** the endpoint is queried
- **THEN** the response SHALL NOT include `eta_first_data` (omitted or `null`)

### Requirement: Calibration page

The frontend SHALL provide a `/calibration` page accessible from the main navigation, showing the per-transition-type success rate table sourced from `/api/v1/calibration/by-transition-type`.

#### Scenario: Empty state with honest copy

- **GIVEN** the endpoint returns `total_resolved = 0`
- **WHEN** the operator opens `/calibration`
- **THEN** the page SHALL display an explicit header card indicating no resolved observations exist yet
- **AND** the header SHALL mention `total_pending` count and `eta_first_data` if present
- **AND** the table SHALL still render with all transition types in `no_data` or `insufficient` status

#### Scenario: Populated state shows stats summary

- **GIVEN** the endpoint returns `total_resolved >= 1`
- **WHEN** the operator opens `/calibration`
- **THEN** the page header SHALL display `total_observations`, `total_resolved`, and `count of transition_types with status='empirical'`

#### Scenario: Status badges differentiate rows

- **WHEN** the page renders the table
- **THEN** each row SHALL display a status badge with distinct visual treatment for `empirical` (green), `insufficient` (amber), and `no_data` (gray)
- **AND** rows with `status='insufficient'` SHALL display the remaining observations needed: `min_samples_required - n_resolved`

#### Scenario: Row ordering

- **WHEN** the page renders the table
- **THEN** rows SHALL be ordered first by status (empirical → insufficient → no_data) and second by `n_resolved` descending within each status group

