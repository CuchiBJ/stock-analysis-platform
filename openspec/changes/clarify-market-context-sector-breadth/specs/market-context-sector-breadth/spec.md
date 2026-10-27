## ADDED Requirements

### Requirement: Sector denominators use the annual eligible universe
The opt-in constituent response SHALL include eligible_symbols and excluded_symbols per sector using the exact existing annual coverage decision. All universe sectors SHALL be present, even without events. Default breadth and current endpoint contracts MUST remain unchanged.

#### Scenario: Sector without extremes
- **WHEN** a sector contains10 annual-eligible stocks but no highs or lows
- **THEN** it appears with eligible_symbols10, empty event arrays and the applicable excluded count

#### Scenario: Dual event and excluded stock
- **WHEN** one eligible stock makes both extremes and another stock is excluded for incomplete history
- **THEN** the first is counted once in eligible_symbols and once on each side, while the second contributes only to excluded_symbols
- **AND** global and sector eligible/excluded/event totals reconcile

#### Scenario: Unavailable sector metadata
- **WHEN** a universe stock has absent or blank sector metadata
- **THEN** it belongs to Sin sector without being lost from coverage

### Requirement: Incidence and concentration have explicit denominators
The page SHALL distinguish each side's rate among eligible stocks from concentration of events among sectors. No rate SHALL be fabricated when coverage is missing or zero.

#### Scenario: Different sector sizes
- **WHEN** sectorA has6 highs among100 eligible and sectorB has3 among10
- **THEN** they show6% and30% respectively, and sorting by high rate placesB first

#### Scenario: Concentrated new highs
- **WHEN** two sectors have6 highs each and total highs are15 with reconciled sector counts
- **THEN** the summary identifies those sectors and shows12/15 (80%) of new-high events
- **AND** it does not call this80% of the market or sector strength

#### Scenario: Incomplete or zero evidence
- **WHEN** sector denominator is absent or zero
- **THEN** counts remain visible but rates and bars are unavailable with an explicit coverage label
- **WHEN** total events are zero with positive coverage
- **THEN** the page distinguishes no events from no coverage

### Requirement: Accessible comparison retains constituent details
The page SHALL show paired comparable bars on fixed0–100% scales, a labeled sorting control and keyboard-operable sector disclosures with stock links. Previous Market context improvements and Dashboard MUST remain intact.

#### Scenario: Change ordering and inspect stocks
- **WHEN** user sorts by low rate and expands a sector
- **THEN** sectors reorder deterministically, counts remain unchanged and high/low constituent lists remain accessible

#### Scenario: Legacy response
- **WHEN** sector arrays have no denominator fields
- **THEN** stock lists and counts render safely and unknown rates sort last without fabricated percentages
