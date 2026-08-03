## ADDED Requirements

### Requirement: Market health presentation distinguishes pullbacks from relapses

The Market Context bar and drawer SHALL present daily health severity and rolling recovery progress compactly, without adding a new analytics card.

#### Scenario: Damage strip encodes three severities

- **WHEN** the health series contains clean, mild, and severe sessions
- **THEN** the damage strip SHALL render clean sessions neutral, mild sessions amber, and severe sessions red
- **AND** each cell tooltip SHALL identify its severity and descriptors

#### Scenario: Drawer explains tolerant recovery progress

- **WHEN** the drawer renders a `DAMAGED` or `FRAGILE` health block
- **THEN** it SHALL show the clean-session count over the rolling seven-session window and the severe-session count over the latest three
- **AND** its explanation SHALL state that five clean of seven and zero severe of three unlock `RECOVERING`

#### Scenario: Existing health information remains visible

- **WHEN** the severity-aware health block renders
- **THEN** the existing health state, damaged-day count, episode count, and trailing clean streak SHALL remain available
