## MODIFIED Requirements

### Requirement: Compact setup card MUST keep visible element count under fifteen per instance

The compact setup card used by Setups Forming SHALL render at most 15 visible elements per card, counting each badge, icon, label, numeric value, narrative, or metric token visible without interaction. The default card SHALL prioritize preparation evidence: symbol/price, formation state, one concise narrative, distance to the next trigger, structure/contraction evidence, RS direction, and primary risk.

#### Scenario: Default formation render stays compact

- **WHEN** a Setups Forming card receives complete nominal data
- **THEN** it SHALL render at most 15 countable visible elements
- **AND** it SHALL remain scannable across a maximum of six cards

#### Scenario: Detailed score evidence is progressively disclosed

- **WHEN** the operator requests more detail or navigates to the symbol page
- **THEN** the full component breakdown and raw values SHALL be available without adding them all to the base dashboard card

### Requirement: Compact setup card MUST NOT render constant or hardcoded chrome

The component SHALL omit values that are constant, duplicate another element, or imply execution when used by Setups Forming. It SHALL NOT render continuation probability, prediction/confidence language, a hardcoded transition, or a fresh/aging/stale/extended badge derived from structural age.

#### Scenario: Formation card does not imply an entry signal

- **WHEN** a Setups Forming card renders
- **THEN** it SHALL use preparation language
- **AND** it SHALL NOT display `actionable`, `buy`, `confidence`, or equivalent recommendation copy

#### Scenario: Structural age is not presented as freshness

- **WHEN** `structural_age_days` is available
- **THEN** the compact card SHALL either omit it or label it explicitly as structural maturity
- **AND** it SHALL NOT map the value to the old freshness badge

#### Scenario: Constant values are omitted

- **WHEN** a card value is constant across every Setups Forming candidate or duplicates the formation-state label
- **THEN** the component SHALL omit that value from its visible base render
