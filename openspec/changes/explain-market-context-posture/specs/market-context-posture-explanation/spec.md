## ADDED Requirements

### Requirement: Visible authoritative posture explanation
The dedicated page SHALL show the backend posture with visible, deterministic evidence separating level, direction and damage memory. It MUST NOT recompute posture or change Dashboard. Original reasons and policy SHALL remain auditable.

#### Scenario: Expansion inside damaged defensive context
- **WHEN** posture is FUERA, base is DEFENSIVO, health is DAMAGED and both descriptors expand
- **THEN** the visible summary explains recent improvement alongside defensive levels and damage memory
- **AND** level values, directional changes with correct units, and damaged session counts are visible without disclosure interaction

#### Scenario: Clean session does not imply fresh damage
- **WHEN** health series has severity clean on context.as_of while posture is FUERA
- **THEN** primary copy says the current session has no classified damage and does not assert active damage today
- **AND** original service copy remains only in explicitly labeled audit disclosure

#### Scenario: Missing current session
- **WHEN** series has no dated severity for context.as_of
- **THEN** current damage is shown as unknown rather than inferred from an older session

#### Scenario: Limited continuity
- **WHEN** follow-through is NOT_PAYING with final posture FUERA
- **THEN** continuity is explained as a ceiling of SELECTIVO, not the sole cause of FUERA

### Requirement: Recovery conditions are explicit and distinct
For DAMAGED or FRAGILE health the page SHALL display health repair evidence; only for DAMAGED it SHALL additionally show early SELECTIVO protection gates and alternative confirmation evidence. Missing evidence MUST NOT count as satisfied. The page MUST NOT promise an upgrade or invent a recovery percentage.

#### Scenario: Repair pending
- **WHEN** repair has 1 clean of 7, requires 5, and has 2 severe of the last 3
- **THEN** it shows the full window as satisfied, clean count and severe absence as pending with actual and required values

#### Scenario: Incomplete repair window
- **WHEN** five clean sessions are observed in a five-session repair window
- **THEN** it does not show the seven-session window requirement as satisfied

#### Scenario: Exceptional evidence cannot bypass defensive levels
- **WHEN** exceptional recovery is true or confirmation streak meets its requirement but base is DEFENSIVO or recent severe count is positive
- **THEN** the relevant protective gate is visibly pending and the page does not state recovery is unlocked

#### Scenario: Retained exception is an alternative
- **WHEN** exceptional_retained is true but current exceptional recovery is false and confirmation streak is below requirement
- **THEN** alternative confirmation evidence is satisfied while independent protections still remain visible

#### Scenario: No health repair checklist for robust market
- **WHEN** health is ROBUST or RECOVERING
- **THEN** the page retains the authoritative posture explanation without DAMAGED/FRAGILE repair checklists

### Requirement: Conservative partial data and scoped integration
Unknown, missing and nonfinite metrics SHALL render as unavailable without invented zeros or thresholds. The implementation SHALL preserve the data-freshness iteration, API, authentication, policy and other page sections.

#### Scenario: Legacy or partial response
- **WHEN** policy or optional recovery evidence is absent
- **THEN** posture remains visible with an incomplete-evidence explanation and no fabricated satisfied gates

#### Scenario: API immutability
- **WHEN** explanation is built and rendered
- **THEN** original state, instruction, reasons, unlock and all input data remain unchanged
