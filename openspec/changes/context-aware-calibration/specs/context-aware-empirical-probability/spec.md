## ADDED Requirements

### Requirement: Empirical probability SHALL prefer comparable cohorts

The system SHALL calculate empirical continuation probability as delivery rate using the actual operational transition, current 21-day window, current regime, and RS bucket, with a deterministic minimum-sample fallback ladder. NEUTRAL outcomes SHALL remain in the probability denominator.

#### Scenario: Most specific cohort is sufficient

- **WHEN** transition + current 21-day window + current regime + RS bucket has at least 20 settled outcomes
- **THEN** its delivery rate SHALL be returned as the empirical probability
- **AND** the result SHALL identify that cohort as its basis

#### Scenario: Specific cohort is insufficient

- **WHEN** the most specific recent cohort has fewer than 20 settled outcomes
- **THEN** lookup SHALL try recent transition at 30, transition + regime + RS at 20, transition + regime at 30, transition + RS at 30, and transition-only at 50 in that order

#### Scenario: No cohort is trustworthy

- **WHEN** no cohort meets its required sample threshold or transition is STABLE
- **THEN** the setup SHALL use the existing interpretable rule-based probability
- **AND** its source SHALL be `rule_based`

### Requirement: Actionable setups SHALL pass their actual transition to calibration

The actionable setups endpoint SHALL derive each candidate's transition from its current and prior metrics rows and SHALL pass that transition and current regime to continuation probability lookup.

#### Scenario: Candidate has a calibrated transition

- **WHEN** a candidate's actual transition has a sufficient comparable cohort
- **THEN** its response SHALL expose `probability_source = empirical`, the cohort sample size, and the empirical basis

#### Scenario: Candidate is stable or lacks prior metrics

- **WHEN** a candidate transition is STABLE or prior metrics are unavailable
- **THEN** its response SHALL use the rule-based fallback without inventing an empirical mapping

#### Scenario: Candidate lookup avoids per-symbol database reads

- **WHEN** the actionable endpoint evaluates multiple candidates
- **THEN** prior metric rows SHALL be fetched in bulk before per-candidate transition calculation
