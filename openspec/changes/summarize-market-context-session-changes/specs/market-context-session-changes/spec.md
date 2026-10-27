## ADDED Requirements
### Requirement: Dated comparable session pair
The summary SHALL use the context date and preceding stored SPY date only when the SPY quote matches context; it SHALL display both dates and the stored-history limitation. All comparisons MUST match exactly that pair.
#### Scenario: Missing reference
- **WHEN** SPY is stale or its previous date is missing, invalid or not earlier
- **THEN** no dimension claims a session change and absence is explained
#### Scenario: Missing immediate metric
- **WHEN** an evolution metric lacks either exact-date observation
- **THEN** that metric is unavailable without substituting an older observation
### Requirement: Deterministic evidence-first changes
The page SHALL summarize participation, leaders, posture, SPY, QQQ and VIX, ordering deterioration before improvement, unchanged and unavailable. Every conclusion MUST expose dated before/after values and the delta or an unavailable reason. Changes SHALL be descriptive and independent of policy/scoring.
#### Scenario: Mixed movement
- **WHEN** participation declines and leaders increase
- **THEN** participation appears first with a percentage-point delta and leaders with a count delta
#### Scenario: Volatility mismatch
- **WHEN** VIX preceding date differs from the reference previous date
- **THEN** VIX is unavailable for comparison even if its current close is aligned
#### Scenario: Posture history absent
- **WHEN** issued historical posture snapshots are absent
- **THEN** posture comparison is explicitly unavailable and is not reconstructed from health
#### Scenario: Partial coverage or refresh failure
- **WHEN** values are invalid, missing, conflicting duplicates, or VIX is loading or failed
- **THEN** unavailable reasons or refresh warnings are explicit and no absent value becomes zero
### Requirement: Additive isolated integration
The system SHALL expose previous_date and previous_price for benchmark and VIX evidence without altering existing dashboard responses, policy or scoring. The dedicated page SHALL disclose variable daily coverage and preserve authentication/loading/error behavior.
#### Scenario: Legacy response
- **WHEN** previous-close fields are absent
- **THEN** the page remains usable and labels comparison unavailable
