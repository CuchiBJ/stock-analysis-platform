## ADDED Requirements

### Requirement: Formation ranking SHALL prioritize preparation evidence instead of structural-state freshness

The priority layer used by Setups Forming SHALL rank only candidates that already passed institutional eligibility and invalidation. It SHALL use the five documented formation components and SHALL NOT use `days_in_state` or the former actionable freshness buckets as a score input.

#### Scenario: New opportunity inside an old structure is not buried by age

- **GIVEN** a candidate has `structural_age_days >= 21`
- **AND** its price is converging toward the EMA trigger zone with intact structure and orderly contraction
- **WHEN** its formation score is calculated
- **THEN** structural age SHALL contribute no penalty
- **AND** readiness evidence SHALL determine its rank

### Requirement: Formation ranking SHALL retain RS as context rather than eligibility

The formation score SHALL allocate 10% to five-session relative-strength trajectory. Missing history SHALL be neutral, and weak or deteriorating RS SHALL reduce the score and surface as a risk, but SHALL NOT be a standalone hard rejection when institutional structure remains valid.

#### Scenario: Weak RS candidate can remain visible with an explicit risk

- **GIVEN** a candidate passes structural and invalidation gates
- **AND** its five-session RS trajectory is deteriorating
- **WHEN** it still reaches the minimum formation score through stronger readiness, structure, and contraction evidence
- **THEN** it SHALL remain rankable
- **AND** the response SHALL identify deteriorating RS as its primary risk

### Requirement: Formation ranking SHALL expose the evidence needed to audit rank

Each ranked candidate SHALL expose raw score, final score, component contributions, trigger-distance inputs, relevant prior-session inputs, context/group contribution, structural age, rank, eligible count, and cutoff status.

#### Scenario: Candidate below the top-six cutoff remains diagnosable

- **GIVEN** a candidate passes eligibility and minimum score but ranks seventh
- **WHEN** its symbol diagnostic is requested
- **THEN** the diagnostic SHALL report `eligible_below_cutoff`
- **AND** it SHALL expose rank 7, eligible count, score breakdown, and the score of the sixth-ranked candidate

## REMOVED Requirements

### Requirement: Top Actionable SHALL grade 52-week-high distance instead of hard-excluding it

**Reason**: The Top Actionable product surface and endpoint are replaced by Setups Forming. The useful principle—52-week-high distance is context rather than a cliff—is carried into the new formation eligibility contract.

**Migration**: In-repository consumers SHALL use `/api/v1/transitions/forming` and `formation_score`; the Setup Feed retains its own stricter near-high rules where already specified.

### Requirement: Actionable ranking SHALL use independent RS leadership during pullback

**Reason**: The old actionable score is retired. Five-session RS remains useful but becomes a smaller, non-gating formation-risk component so it cannot bury otherwise timely pre-signal candidates by itself.

**Migration**: Reuse the pure RS-history helper where appropriate, map its output to the 10% formation component, and remove actionable-only score wiring.
