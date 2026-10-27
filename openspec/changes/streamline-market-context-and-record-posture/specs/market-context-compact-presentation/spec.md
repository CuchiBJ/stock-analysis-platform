## ADDED Requirements

### Requirement: Posture header exposes essential context first
The dedicated page SHALL display authoritative posture, instruction, synthesis, current damage and continuity while placing levels, detailed gates and audit evidence in an initially closed accessible disclosure.

#### Scenario: Defensive posture with repair evidence
- **WHEN** FUERA includes damage memory and repair gates
- **THEN** the first view includes the summary, current damage and continuity and the detailed thresholds/gates remain accessible in a closed native disclosure

#### Scenario: Missing evidence
- **WHEN** damage or posture evidence is unavailable
- **THEN** unknown evidence stays explicit and no prior session is borrowed or decision recalculated

### Requirement: Sector history supports compact comparison and single-sector detail
The page SHALL render a compact semantic comparison of all sectors, actual rates, signed changes and coverage, with at most one sector history panel expanded on demand.

#### Scenario: Compare twelve sectors
- **WHEN** complete five-session sector history is supplied
- **THEN** the default view contains all sector summary rows and no expanded graphs, and identifies the dates for rates and changes

#### Scenario: Select or close a sector
- **WHEN** the user activates a sector by keyboard or pointer
- **THEN** its dated history, fixed-scale graphs and coverage evidence become visible and any previously selected sector closes
- **AND** activating the selected sector again closes its detail

#### Scenario: Refresh or sparse coverage
- **WHEN** selected data refreshes or lacks observations
- **THEN** selection is retained by sector name only while that sector exists and unavailable rates/deltas remain distinct from zero
