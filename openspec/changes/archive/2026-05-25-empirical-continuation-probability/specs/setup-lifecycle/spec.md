## MODIFIED Requirements

### Requirement: Continuation Probability SHALL Be a Weighted Composite

`calculate_continuation_probability(metrics, context=None)` SHALL return a
tuple `(probability, source, sample_size)` where:

- `probability` is a value in `[0, 1]`
- `source` is one of `"empirical"` or `"rule_based"`
- `sample_size` is an integer ≥ 0

The function SHALL first attempt an empirical lookup via the
`empirical-probability` capability using:
- `transition_type` derived from the metrics' detected state transition
- `rs_bucket` derived from `relative_strength_spy`
- `participation_descriptor` from the optional `context` argument (or
  `UNKNOWN` if not provided)

If the empirical lookup returns a result with `sample_size ≥ 5`, the function
SHALL return that result with `source = "empirical"`.

Otherwise, the function SHALL fall back to the weighted-composite formula
(unchanged from previous spec version) and return that value with
`source = "rule_based"` and `sample_size = 0`. The composite weights are:

| Component              | Weight | Source field                  |
|------------------------|--------|-------------------------------|
| Weekly trend quality   | 40%    | `weekly_trend_quality`        |
| Pullback quality score | 30%    | `pullback_quality_score / 100`|
| Relative strength      | 20%    | `relative_strength_spy` (tiered) |
| Volume contraction     | 10%    | `volume_contraction`          |

RS tiering (unchanged):
- ≥ 115: +0.20
- ≥ 110: +0.16
- ≥ 105: +0.12
- ≥ 100: +0.08
- ≥ 95:  +0.04
- < 95:  +0.00

**Implementation:** `setup_lifecycle_engine.py` — `calculate_continuation_probability`

#### Scenario: Empirical cohort with enough samples wins over formula

- **GIVEN** metrics with `relative_strength_spy = 112` and a detected transition
  matching a cohort with 18 historical observations (12 SUCCESS, 6 FAILURE)
- **WHEN** `calculate_continuation_probability(metrics, context)` is called
- **THEN** the result SHALL be `(0.667, "empirical", 18)`
- **AND** the rule-based formula SHALL NOT have been evaluated

#### Scenario: Strong setup with no empirical history falls back to formula

- **GIVEN** `weekly_trend_quality = 0.9`, `pullback_quality_score = 90`,
  `relative_strength_spy = 115`, `volume_contraction = 0.8`
- **AND** zero historical observations for the matching cohort
- **WHEN** `calculate_continuation_probability(metrics)` is called
- **THEN** the returned `source` SHALL be `"rule_based"`
- **AND** the returned `sample_size` SHALL be `0`
- **AND** the returned `probability` SHALL be > 0.85 (matching the prior formula behavior)

#### Scenario: Missing fields SHALL contribute 0, not error

- **GIVEN** `relative_strength_spy IS NULL` and no empirical cohort match
- **WHEN** `calculate_continuation_probability(metrics)` is called
- **THEN** the function SHALL NOT raise
- **AND** the RS component SHALL contribute 0 to the rule-based total
- **AND** `source` SHALL be `"rule_based"`
