## ADDED Requirements

### Requirement: Pullback outcomes follow support then continuation

The system SHALL classify `entering_pullback` from the first ten ordered completed daily price bars after detection. EMA9, EMA21, and EMA50 SHALL evolve from their saved detection seeds using `alpha = 2 / (period + 1)` and each subsequent close. A support test SHALL require a low at/below EMA9 with a close at/above EMA9, or a low at/below EMA21 with a close at/above EMA21. Wicks below EMA9/EMA21 SHALL be permitted when the tested support recovers at close. SUCCESS SHALL require a strictly later session with a high at least detection price plus 1.5 detection ATR and a close at/above EMA9. A valid window without continuation SHALL be NEUTRAL.

Implementation: `backend/app/services/pullback_outcome.py` and `backend/app/services/outcome_tracker.py`.

#### Scenario: Recovered wick followed by continuation
- **WHEN** a session wicks below EMA21 and closes above it, and a later session within the first ten reaches the 1.5 ATR target while closing above EMA9
- **THEN** the outcome SHALL be SUCCESS if no invalidation occurs in the window

#### Scenario: Advance preceded the support test
- **WHEN** the target was reached only before the recovered support test or on the test's same daily candle
- **THEN** the outcome SHALL NOT be SUCCESS

#### Scenario: Continuation deadline
- **WHEN** continuation first occurs on the tenth subsequent completed bar
- **THEN** it SHALL qualify
- **WHEN** continuation first occurs on the eleventh bar
- **THEN** it SHALL NOT qualify

### Requirement: Invalidation takes precedence over continuation

Any low at/below the evolving EMA50 or close below the evolving EMA21 in the ten-bar window SHALL classify the pullback as FAILURE, even if the price rebounds or continuation previously occurred. A close below EMA9 but at/above EMA21 SHALL NOT alone invalidate the window. Missing, nonfinite, or invalid required detection inputs or OHLC SHALL yield INSUFFICIENT_DATA. Entering pullbacks SHALL NOT fall back to legacy pre-reclaim aggregate classification.

Implementation: `backend/app/services/pullback_outcome.py`.

#### Scenario: EMA50 touch then rebound
- **WHEN** price touches EMA50 intraday and later reaches the continuation target
- **THEN** the outcome SHALL be FAILURE

#### Scenario: EMA21 closing loss
- **WHEN** a session closes below EMA21 and a later session recovers
- **THEN** the outcome SHALL be FAILURE

#### Scenario: Missing support context
- **WHEN** a required detection EMA or ATR is missing or nonfinite
- **THEN** the outcome SHALL be INSUFFICIENT_DATA rather than SUCCESS or NEUTRAL

### Requirement: Evaluation excludes mutable and future sessions

Pullback evaluation SHALL exclude price dates on or after `as_of_date` and SHALL remain PENDING until ten completed subsequent stored daily bars exist. All outcome queries SHALL exclude dates after `as_of_date`. Only the first ten qualifying bars SHALL determine a settled pullback result.

Implementation: `backend/app/services/outcome_tracker.py`.

#### Scenario: Tenth bar is still mutable
- **WHEN** nine completed subsequent bars and today's daily bar exist
- **THEN** the pullback SHALL remain PENDING

### Requirement: Historical pullbacks are recomputed consistently

A data migration SHALL reset only terminal entering-pullback labels and derived outcome fields, preserving detection snapshots. Manual reclassification SHALL recompute entering pullbacks from ordered stored OHLC, including previously insufficient pullbacks, and SHALL preserve the existing aggregate reclassification for all other transitions. Calibration SHALL explain wick recovery, EMA50 invalidation, the retained 1.5 ATR continuation criterion, and the ten-session window.

Implementation: `backend/alembic/versions/`, `backend/app/api/v1/endpoints/calibration.py`, and `frontend/app/calibration/page.tsx`.

#### Scenario: Legacy success used the wrong support
- **WHEN** a terminal entering-pullback outcome was computed under the previous shared rule
- **THEN** the migration SHALL reset it to PENDING and clear derived fields
- **AND** its original price, ATR, EMAs, regime, symbol, and detection dates SHALL remain intact

#### Scenario: Explicit historical reevaluation
- **WHEN** an entering pullback is manually reclassified
- **THEN** the classifier SHALL use its ordered completed price window and discard stale derived values
- **AND** an unrelated transition SHALL retain its existing outcome semantics
