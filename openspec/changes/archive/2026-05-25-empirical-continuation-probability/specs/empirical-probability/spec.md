## ADDED Requirements

### Requirement: Empirical Probability Replaces Hardcoded Formula When Possible

The system SHALL compute continuation probability from observed historical
outcomes (`transition_observations.outcome_status`) whenever a cohort with
sufficient sample size exists. The system SHALL fall back to the rule-based
formula ONLY when no cohort level meets the minimum sample threshold.

The empirical probability is defined as:

```
success_rate = COUNT(outcome_status = 'SUCCESS')
             / COUNT(outcome_status IN ('SUCCESS', 'FAILURE'))
```

`NEUTRAL` outcomes are EXCLUDED from both numerator and denominator. A
transition that resolves to neither a clear success nor a clear failure is
genuinely ambiguous and SHALL NOT inflate or deflate the rate. `PENDING`
and `INSUFFICIENT_DATA` are also excluded.

#### Scenario: Cohort with enough samples returns empirical probability

- **GIVEN** 10 historical observations of `RECLAIM_PREPARATION → RECLAIM_IN_PROGRESS`
  with `rs_bucket = 110-120` and `participation_descriptor = STABLE`
- **AND** 7 of them have `outcome_status = SUCCESS`, 2 are `FAILURE`, 1 is `NEUTRAL`
- **WHEN** `EmpiricalProbabilityCalculator.lookup(...)` is called for a matching setup
- **THEN** the returned probability SHALL be `7 / 9 = 0.778` (NEUTRAL excluded)
- **AND** the returned `sample_size` SHALL be `9`
- **AND** the returned `source` SHALL be `"empirical"`

#### Scenario: NEUTRAL never enters the success-rate calculation

- **GIVEN** 5 observations: 2 SUCCESS, 0 FAILURE, 3 NEUTRAL
- **WHEN** the success rate is computed
- **THEN** the rate SHALL be `2 / 2 = 1.0`
- **AND** the sample_size SHALL be `2`
- **AND** because sample_size is below the minimum threshold, the result SHALL be
  treated as "no cohort match" and trigger fallback

---

### Requirement: Cohort Key and Fallback Ladder Are Explicit

The primary cohort key SHALL be the triple
`(transition_type, rs_bucket, participation_descriptor)`.

RS buckets SHALL be exactly:
- `lt_100` — `relative_strength_spy < 100`
- `100_110` — `100 ≤ rs < 110`
- `110_120` — `110 ≤ rs < 120`
- `gte_120` — `rs ≥ 120`
- `unknown` — `rs IS NULL`

Participation descriptor values SHALL match the
`market-context` capability exactly: `EXPANDING`, `STABLE`, `NARROWING`,
`COLLAPSING`. When market context is unavailable, the value `UNKNOWN` SHALL be
used.

The fallback ladder SHALL be applied in this exact order, stopping at the
first level whose sample size meets the minimum threshold:

1. Full cohort: `(transition_type, rs_bucket, participation_descriptor)`
2. Drop participation: `(transition_type, rs_bucket)`
3. Drop RS: `(transition_type,)`
4. Rule-based fallback (synthetic formula)

The minimum sample-size threshold SHALL be **5 observations** for Phase 1.

#### Scenario: Fallback drops participation when full cohort is sparse

- **GIVEN** the full cohort `(RECLAIM_PREPARATION, 110_120, EXPANDING)` has 2 observations
- **AND** the cohort `(RECLAIM_PREPARATION, 110_120)` has 12 observations
- **WHEN** lookup is called
- **THEN** the system SHALL return the 12-observation cohort result
- **AND** the source SHALL be `"empirical"` (still empirical, just less stratified)
- **AND** the sample_size SHALL be `12`

#### Scenario: Full fallback to rule-based when nothing has 5+ samples

- **GIVEN** zero historical observations of the transition type
- **WHEN** lookup is called
- **THEN** the system SHALL return source `"rule_based"` with sample_size `0`
- **AND** the probability SHALL be the existing weighted-composite formula output

---

### Requirement: Cache and Invalidation Contract

The empirical-probability service SHALL maintain an in-memory cache keyed by
the full cohort triple with a TTL of approximately 10 minutes. The cache SHALL
be invalidated immediately when `outcome_tracker` writes new outcome rows
(transitions moving out of `PENDING`), via an explicit hook call — not via
TTL expiry alone.

The cache MAY be per-process (no shared Redis required in Phase 1). Stale
reads of up to 10 minutes are acceptable while no new outcomes arrive.

#### Scenario: Outcome write invalidates relevant cache entries

- **GIVEN** the cache contains a result for `(RECLAIM_PREPARATION, 110_120, STABLE)`
- **WHEN** `outcome_tracker.evaluate_pending()` writes new outcome rows
- **THEN** the cache SHALL be cleared (Phase 1: clear all entries; future:
  invalidate only affected cohorts)
- **AND** the next lookup SHALL recompute from the database

#### Scenario: Cache hit within TTL avoids database query

- **GIVEN** a cohort was computed at time T and cached
- **WHEN** the same cohort is requested at `T + 60s` and no outcome writes
  have occurred
- **THEN** the cached result SHALL be returned without querying
  `transition_observations`

---

### Requirement: API Responses SHALL Expose Probability Source and Sample Size

Every API endpoint returning `continuation_probability` (or `continuation_prob`) SHALL also return the sibling fields:

- `probability_source`: string, one of `"empirical"` or `"rule_based"`
- `sample_size`: integer, the count of `SUCCESS + FAILURE` observations behind
  the empirical lookup; `0` when source is `"rule_based"`

The probability value itself SHALL remain a float in `[0.0, 1.0]` — only
metadata is added, not changed.

This applies to (at minimum):
- `GET /api/v1/transitions/current`
- `GET /api/v1/queue/ur-queue`
- `GET /api/v1/queue/emerging-leaders`
- `GET /api/v1/queue/building-bases`
- `GET /api/v1/setup-lifecycle/*`

#### Scenario: Every continuation_probability response includes source metadata

- **WHEN** any of the listed endpoints returns a setup with `continuation_probability`
- **THEN** the same object SHALL contain `probability_source` and `sample_size`
- **AND** the absence of either field SHALL be considered a contract violation

#### Scenario: Source flag is honest about its origin

- **GIVEN** the empirical calculator falls back to the rule-based formula
- **WHEN** the response is constructed
- **THEN** `probability_source` SHALL be `"rule_based"`, NOT `"empirical"`
- **AND** `sample_size` SHALL be `0`

---

### Requirement: Frontend Surfaces Probability Source to Operator

The setup card components rendering `continuation_probability` SHALL display
the source of the number near the percentage. When source is `"empirical"`,
the card SHALL show `empirical (N=<sample_size>)` in muted styling. When
source is `"rule_based"`, the card SHALL show `rule-based` in amber styling
to signal that this number is synthetic.

The percentage display itself SHALL NOT change visually based on source —
only the adjacent metadata label.

#### Scenario: Empirical setup shows sample size

- **GIVEN** a setup response with `continuation_probability: 0.72`,
  `probability_source: "empirical"`, `sample_size: 18`
- **WHEN** the setup card renders
- **THEN** the card SHALL display `72%` for the probability
- **AND** the card SHALL display `empirical (N=18)` adjacent to the percentage
  in muted color

#### Scenario: Rule-based setup is visually flagged

- **GIVEN** a setup response with `probability_source: "rule_based"`,
  `sample_size: 0`
- **WHEN** the setup card renders
- **THEN** the card SHALL display `rule-based` in amber color adjacent to
  the percentage
- **AND** the percentage SHALL render normally (color/size unaffected)

---

### Requirement: System SHALL Fall Back to Rule-Based for Unknown Transition Types

The system SHALL fall back to the rule-based formula for transition types with zero historical observations in `transition_observations`, and SHALL NOT return synthetic "empirical" values, SHALL NOT fabricate a default probability, and SHALL NOT raise an exception.

#### Scenario: Unknown transition type returns rule-based fallback

- **GIVEN** a transition type `NEW_HYPOTHETICAL_TRANSITION` with zero rows
  in `transition_observations`
- **WHEN** lookup is called
- **THEN** the result SHALL be source `"rule_based"`, sample_size `0`
- **AND** the probability SHALL be computed from the rule-based formula
- **AND** no exception SHALL be raised
