## ADDED Requirements
### Requirement: Exact-session opposing movements
The dedicated page SHALL evaluate SPY and QQQ separately against participation and leader count using the same validated session-change evidence and rounded directions. Only opposite nonzero directions SHALL produce a divergence finding; unavailable values SHALL never count as unchanged.
#### Scenario: Index advances with weaker internals
- **WHEN** an aligned index rises and participation or leader count falls
- **THEN** a deterioration finding states the opposition and exposes both dated before/after values and deltas
#### Scenario: Internal improvement against falling index
- **WHEN** an aligned index falls and an internal measure rises
- **THEN** a literal descriptive finding appears after deterioration without predicting reversal or changing posture
#### Scenario: Flat or aligned changes
- **WHEN** either side is unchanged at displayed precision or both move in the same direction
- **THEN** the evaluable pair yields no opposing-movement finding
#### Scenario: Dates or observations unavailable
- **WHEN** either side lacks an exact-date comparable value, including legacy fields or conflicting observations
- **THEN** that pair is unevaluable with the reason disclosed and no older observation substituted
### Requirement: Honest coverage and bounded presentation
The section SHALL show evaluated comparisons out of four, no more than four findings in deterministic deterioration-first order, and distinguish full no-findings, partial coverage and zero coverage. It SHALL explain that opposing session movements do not confirm reversal and daily populations can differ.
#### Scenario: Partial evidence
- **WHEN** only SPY and participation have comparable observations
- **THEN** one of four comparisons is evaluated and missing comparisons are explained without claiming global absence of divergence
#### Scenario: No evidence
- **WHEN** no pair can be evaluated
- **THEN** the UI reports insufficient comparable evidence rather than no divergences
#### Scenario: All pairs available without opposition
- **WHEN** all four comparisons are evaluable but no opposite directions occur
- **THEN** the UI reports no opposing movements for these comparisons without inferring a healthy market
### Requirement: Isolated dedicated-page integration
The feature SHALL reuse existing overview evidence without new requests or backend changes, remain under existing authentication/data guards, and leave dashboard, scoring, posture and previous improvements unchanged.
#### Scenario: Missing overview
- **WHEN** the overview is loading, absent or unavailable
- **THEN** existing page states remain authoritative and no fabricated divergence section appears
