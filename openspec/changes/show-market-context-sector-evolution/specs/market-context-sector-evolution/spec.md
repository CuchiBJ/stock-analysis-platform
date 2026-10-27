## ADDED Requirements
### Requirement: Bounded faithfully reconstructed sector history
The protected API SHALL return at most five ascending stored SPY sessions ending exactly at requested as_of with reconciled annual high/low and eligible/excluded counts per sector. It MUST apply existing quality and strict 252-session annual-event rules without future or orphan data and without database writes.
#### Scenario: Missing annual price
- **WHEN** a quality symbol lacks one required annual high/low pair
- **THEN** it is excluded rather than reaching farther back or counted as a zero event
#### Scenario: Reference missing
- **WHEN** SPY has no stored session at as_of
- **THEN** the response is no_reference_session with empty sessions
#### Scenario: Query efficiency and cache
- **WHEN** multiple symbols and five target sessions are present
- **THEN** database queries remain bulk and bounded independent of symbols/sessions, and cached responses cannot be mutated by consumers
#### Scenario: Current-session reconciliation
- **WHEN** history and existing breadth use identical fixture data
- **THEN** current high/low/eligible/excluded counts and sectors agree exactly
### Requirement: Interpretable incidence and concentration changes
The page SHALL show per-sector high/low incidence across sessions with gaps, fixed 0–100 percent scale, counts and denominators. It SHALL compare exact first/last endpoints in percentage points, sort deterioration before improvements, and separately show sector event participation and top-two event concentration.
#### Scenario: Changing denominator
- **WHEN** eligible counts differ between endpoints
- **THEN** both denominators and the coverage change are visible and no identical-population claim is made
#### Scenario: Missing sector or endpoint
- **WHEN** a sector lacks coverage at either endpoint or has conflicting observations
- **THEN** its comparison is unavailable without substituting another date
#### Scenario: No events versus no coverage
- **WHEN** eligible counts are positive but events are zero
- **THEN** incidence is valid zero while concentration is unavailable; zero eligible counts instead mean insufficient coverage
#### Scenario: Intermediate gap
- **WHEN** a sector is absent from an intermediate session
- **THEN** the visualization breaks at that session and the details mark it missing
### Requirement: Honest metadata and isolated UI states
The feature SHALL disclose current sector/market-cap metadata, changing eligible populations and stored-calendar limitations. Loading, refresh failures, legacy API absence and no data SHALL remain isolated to the section. Dashboard and market policy SHALL remain unchanged.
#### Scenario: Historical labels
- **WHEN** historical observations are displayed
- **THEN** methodology states they use current sector and market-cap metadata rather than historical composition
#### Scenario: Endpoint unavailable
- **WHEN** sector history fails or is unavailable
- **THEN** existing overview remains visible and the section displays an explicit retry/unavailable state
