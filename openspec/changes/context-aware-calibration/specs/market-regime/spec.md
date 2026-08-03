## MODIFIED Requirements

### Requirement: Regime Detection SHALL Use Five Contributing Factors

`MarketRegimeAnalysis` SHALL include all five factors with values in [0, 1]:

1. **Breadth quality** — % of stocks above EMA50 (70%) + % near 52w highs (30%)
2. **Leadership health** — % of leaders (pullback_quality ≥ 60) above EMA21 (70%) + % with RS ≥ 105 (30%)
3. **Speculative appetite** — average ADR% normalized: `(avg_adr - 1) / 4`, clamped to [0, 1]
4. **Sector expansion** — % of stocks with positive 1-week performance
5. **Pullback environment quality** — average `pullback_quality_score` / 100

All five SHALL use `QUALITY_FILTERS` and the same single `stock_metrics` date resolved at or before the requested `as_of`. No regime factor SHALL aggregate multiple historical snapshots.

#### Scenario: Current detection uses latest snapshot

- **WHEN** `detect_regime()` is called without a target date
- **THEN** it SHALL resolve the maximum available `stock_metrics.date`
- **AND** every factor query SHALL filter to that date

#### Scenario: Historical detection avoids lookahead

- **WHEN** `detect_regime(target)` is called
- **THEN** it SHALL use the maximum available metrics date less than or equal to `target`
- **AND** SHALL NOT read a later snapshot

#### Scenario: Empty database returns neutral defaults

- **WHEN** no metrics date exists at or before the target
- **THEN** all five factors SHALL equal `0.5`
- **AND** the regime SHALL be `choppy`
