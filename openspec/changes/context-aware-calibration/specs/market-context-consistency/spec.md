## ADDED Requirements

### Requirement: Market context SHALL own the as-of regime

`MarketContextEngine` SHALL calculate regime for the same resolved `as_of` used by participation, leadership, health, and follow-through. Downstream current-context consumers SHALL reuse this regime analysis.

#### Scenario: Current context dimensions share one date

- **WHEN** current market context is analyzed
- **THEN** `ctx.regime.as_of` SHALL equal `ctx.as_of`
- **AND** the market-context API SHALL expose the regime and its five factor values

#### Scenario: Calibration reuses market context regime

- **WHEN** Calibration builds the current-regime cohort
- **THEN** it SHALL use `market_context.regime.regime`
- **AND** SHALL NOT independently calculate another current regime

#### Scenario: Actionable scoring reuses market context regime

- **WHEN** actionable setups are ranked
- **THEN** their regime alignment and empirical lookup SHALL use the regime from the same market context snapshot as participation and leadership

### Requirement: NOT_PAYING SHALL always be explained

The posture engine SHALL include the recent-signals-not-paying reason whenever follow-through is `NOT_PAYING`, even when health or market anatomy has already produced `SELECTIVO`, `DEFENSIVO`, or `FUERA`.

#### Scenario: Defensive posture retains follow-through evidence

- **WHEN** anatomy or health produces `DEFENSIVO` and follow-through is `NOT_PAYING`
- **THEN** posture SHALL remain `DEFENSIVO`
- **AND** its reasons SHALL include current and baseline delivery when available
