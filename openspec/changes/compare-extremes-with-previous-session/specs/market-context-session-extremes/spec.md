## ADDED Requirements
### Requirement: Previous-session extremes
Market Context SHALL count strict highs and lows relative to the immediately preceding stored SPY session, using valid current and previous high/low pairs and the existing quality universe. The API SHALL name this comparison new_session_highs_vs_lows.
#### Scenario: Daily breakout below annual high
- **WHEN** a current high exceeds the previous session high but remains below an older high
- **THEN** it counts as a new session high without requiring annual history
#### Scenario: Ties and dual events
- **WHEN** prices tie previous extremes or exceed both sides
- **THEN** ties count no event and a dual event counts once on each side with one eligible symbol
#### Scenario: Missing or invalid previous pair
- **WHEN** the required previous session price is absent or invalid
- **THEN** the symbol is excluded without substituting an older or orphan row
### Requirement: Consistent presentation and history
The page, drawer, constituents and sector evolution SHALL use the same previous-session definition and explain it. Annual benchmark and proximity metrics SHALL retain their original definitions.
#### Scenario: Reconciliation
- **WHEN** current breadth and sector history use identical data
- **THEN** counts and coverage agree and no session comparison is labeled 52 weeks
