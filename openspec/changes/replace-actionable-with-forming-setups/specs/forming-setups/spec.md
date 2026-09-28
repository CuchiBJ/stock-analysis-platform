## ADDED Requirements

### Requirement: Setups Forming SHALL be a preparation surface distinct from the Setup Feed

The system SHALL expose `GET /api/v1/transitions/forming` as a protected endpoint returning institutional-quality setups that are preparing for, but do not currently have, a qualifying non-stable transition in the Setup Feed. The dashboard SHALL label the panel `Setups Forming` and SHALL present it before the Setup Feed in reading order, while describing the Setup Feed as the execution surface.

#### Scenario: Current feed symbol is not duplicated

- **GIVEN** a symbol is returned by the current Setup Feed snapshot
- **WHEN** Setups Forming is calculated for the same metrics snapshot
- **THEN** the symbol SHALL NOT appear in Setups Forming
- **AND** its symbol diagnostic SHALL report `promoted_to_feed`

#### Scenario: Candidate returns after transition episode ends

- **GIVEN** a structurally valid symbol was previously promoted to the Setup Feed
- **AND** its current snapshot no longer produces a qualifying non-stable transition
- **WHEN** it still passes formation eligibility and minimum score
- **THEN** it MAY appear again in Setups Forming

### Requirement: Formation eligibility SHALL preserve institutional structure without a near-high hard gate

Every formation candidate SHALL use the latest metrics snapshot and pass canonical `QUALITY_FILTERS`, market capitalization of at least $600M, `perf_1y > 30`, price above EMA50 and SMA150, SMA150 above SMA200, and price at least `1.5 × low_52w`. The system SHALL NOT use `distance_to_high_52w_atr` or current EMA9/EMA21 trigger membership as a hard eligibility condition.

#### Scenario: BE-shaped pullback remains eligible beyond three ATR from its high

- **GIVEN** a candidate passes every structural and quality condition
- **AND** `distance_to_high_52w_atr = -4.35`
- **AND** the candidate is not invalidated and is not currently in the Setup Feed
- **WHEN** formation eligibility is evaluated
- **THEN** 52-week-high distance SHALL NOT exclude it
- **AND** the response SHALL expose that distance as context

#### Scenario: Broken long-term structure is excluded

- **GIVEN** a candidate is near an EMA trigger
- **AND** SMA150 is not above SMA200
- **WHEN** formation eligibility is evaluated
- **THEN** the candidate SHALL be excluded before scoring

### Requirement: Deterioration SHALL be evaluated before formation scoring

The formation pipeline SHALL run the existing setup invalidation logic and current lifecycle deterioration checks before calculating a positive formation score. A candidate classified as `BROKEN`, `DISTRIBUTION`, or invalidated for any hard reason SHALL NOT be ranked.

#### Scenario: Attractive proximity cannot rescue distribution

- **GIVEN** a candidate is close to EMA9 and has strong weekly tightness
- **AND** current metrics classify it as `DISTRIBUTION`
- **WHEN** the formation pipeline runs
- **THEN** it SHALL be excluded before score calculation
- **AND** the exclusion reason SHALL be inspectable

### Requirement: Formation ranking SHALL be deterministic and explainable

Each eligible candidate SHALL receive a `formation_score` in `[0, 100]` composed of trigger readiness/direction (35%), structural integrity (25%), orderliness/contraction (20%), relative-strength trajectory (10%), and regime/group alignment (10%). Every response item SHALL include the component breakdown, key raw inputs, a concise formation narrative, and the primary risk.

#### Scenario: Structural age does not reduce formation score

- **GIVEN** two otherwise identical candidates with structural ages of 3 days and 25 days
- **WHEN** their formation scores are calculated
- **THEN** both SHALL receive the same formation score
- **AND** each response MAY expose its distinct `structural_age_days` as context

#### Scenario: Missing RS history is neutral

- **GIVEN** an eligible candidate has no five-session RS baseline
- **WHEN** its relative-strength trajectory component is calculated
- **THEN** the component SHALL use a neutral value
- **AND** missing history SHALL NOT exclude or promote the candidate

#### Scenario: Breakdown sums to final score

- **WHEN** a formation item is returned
- **THEN** its weighted component contributions SHALL sum to the reported pre-clamp score
- **AND** its final `formation_score` SHALL equal that score clamped to `[0, 100]`

### Requirement: Setups Forming SHALL enforce scarcity

The endpoint SHALL return at most six candidates, ordered by formation score descending, then trigger proximity, then structural integrity. The default minimum formation score SHALL be 55. The system SHALL return an empty list rather than lower eligibility or score thresholds.

#### Scenario: More than six candidates qualify

- **GIVEN** ten candidates have formation scores at or above 55
- **WHEN** the endpoint is called with its default limit
- **THEN** it SHALL return exactly the highest-ranked six

#### Scenario: No candidate reaches the threshold

- **GIVEN** no eligible candidate has a formation score of at least 55
- **WHEN** the endpoint is called
- **THEN** it SHALL return an empty results array with a healthy context snapshot
- **AND** the frontend SHALL communicate that no setups are forming without relaxing thresholds

### Requirement: Formation cards SHALL communicate preparation rather than execution

Each card SHALL show symbol, current price context, formation narrative, distance to the next relevant EMA trigger, structural/contraction evidence, RS direction, and the primary risk. It SHALL NOT show buy language, continuation probability, prediction confidence, or a fresh/stale badge derived from structural state age.

#### Scenario: Operator can distinguish preparation from a signal

- **WHEN** a formation card is rendered
- **THEN** its copy SHALL describe what is forming and what evidence is still missing
- **AND** it SHALL NOT describe the candidate as actionable or as an entry signal
