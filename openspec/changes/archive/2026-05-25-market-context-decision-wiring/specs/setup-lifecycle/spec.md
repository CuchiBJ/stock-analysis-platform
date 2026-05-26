## ADDED Requirements

### Requirement: Actionable Setup Response SHALL Expose Context Multiplier Effect

The `/api/v1/transitions/actionable` response SHALL reflect the
`context-decision-filter` decision on every setup. Specifically:

- The response top level SHALL include a `context_snapshot` object with
  fields `participation: string` and `leadership: string`, sourced from
  the `MarketContextEngine` at request time.
- Each setup in the result SHALL include a `context_warnings: list[str]`
  field. The list SHALL be empty when no warnings apply.
- The `priority_score` returned in each setup SHALL already incorporate
  the context multiplier (server-side) — clients SHALL NOT apply any
  multiplier on top.

The setup's `continuation_prob`, `probability_source`, and `sample_size`
fields (added in `empirical-continuation-probability`) remain unchanged —
context multiplier affects ranking, not the empirical lookup.

#### Scenario: Hostile context multiplies scores down on the server

- **GIVEN** the upstream context yields `score_multiplier = 0.7`
- **AND** a setup whose pre-multiplier `priority_score` would be `0.80`
- **WHEN** `/api/v1/transitions/actionable` is called
- **THEN** the setup's `priority_score` in the response SHALL be `0.56`
- **AND** the client SHALL render that value as-is without re-multiplying

#### Scenario: EXHAUSTED leadership produces a warning on every setup

- **GIVEN** the current `leadership = "EXHAUSTED"`
- **WHEN** the endpoint responds
- **THEN** every setup's `context_warnings` SHALL contain `"leadership_exhausted"`

#### Scenario: Benign context produces empty warnings

- **GIVEN** `participation = "STABLE"` and `leadership = "HEALTHY"`
- **WHEN** the endpoint responds
- **THEN** each setup's `context_warnings` SHALL be `[]`
- **AND** the `priority_score` SHALL be unchanged from the pre-multiplier value (multiplier is 1.0)
