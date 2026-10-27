## ADDED Requirements

### Requirement: Capture current posture after successful session processing
The scheduler SHALL await durable capture of the current market posture after the existing post-close prices and metrics cycle, without requiring current/overview requests. The cycle SHALL qualify only with more than 0 covered symbols and at least 95% coverage of its own attempted-symbol snapshot; a skipped overlapping SLOW run SHALL NOT qualify. The stored payload SHALL retain state, instruction, reasons, unlock and policy with an actual UTC observation timestamp.

Implementation: `backend/app/data/scheduler.py`, a focused post-close coordinator under `backend/app/data/`, and `backend/app/services/market_posture_record_service.py`.

#### Scenario: No users visit during the session
- **WHEN** post-close processing completes with sufficient coverage and a valid current posture
- **THEN** one durable posture record exists for that exact session even with no HTTP requests
- **AND** repeated captures retain one latest-observation row using the existing atomic upsert

#### Scenario: Incomplete or overlapping work
- **WHEN** SLOW is skipped, covers 0 symbols, or covers less than 95% of its attempted snapshot
- **THEN** the cycle does not capture posture or report successful completion

### Requirement: Preserve exact session and fresh calculation evidence
Automatic capture SHALL calculate current context without reusing pre-pipeline caches. Its post-close metrics run SHALL NOT skip recalculation because a metric row was recently updated before EOD prices were loaded; ordinary SLOW write protection SHALL remain compatible. It SHALL require the context date to equal the cycle target session, a nonempty quality universe, and a known valid posture. It SHALL NOT reconstruct historical posture, relabel stale data as the target date, or synthesize missing earlier sessions. Existing API response bodies and request-driven observation SHALL remain compatible.

Implementation: `backend/app/services/market_context_engine.py` and the focused capture coordinator/service.

#### Scenario: Fresh metrics replace a cached posture
- **WHEN** the current session has a cached context from before new metrics were committed
- **THEN** pipeline capture recomputes current context from committed metrics and stores that resulting posture

#### Scenario: Recently calculated metrics precede EOD prices
- **WHEN** metrics were written within 5 minutes before the post-close cycle loaded EOD prices
- **THEN** the post-close metrics run recalculates them before posture capture instead of accepting the pre-EOD fresh-row skip

#### Scenario: Stale or invalid context
- **WHEN** current context is missing, belongs to an earlier or future date, has an empty quality universe, or has no valid posture
- **THEN** no record is manufactured and the cycle remains unsuccessful

### Requirement: Isolate failures and retry within the session
The scheduler SHALL expose unsuccessful capture in its existing post_close_cycle heartbeat/log and continue its other work without undoing committed metrics. It SHALL mark the session complete only after capture succeeds. Failed attempts SHALL be retried no more often than every 300 seconds during the existing weekday post-close window for the same New York calendar day; successful sessions SHALL NOT be retriggered within that process. Existing request capture and history comparison SHALL continue to work.

Implementation: `backend/app/data/scheduler.py`, the post-close coordinator and targeted offline tests.

#### Scenario: Database or calculation failure
- **WHEN** posture calculation or persistence fails after metrics are committed
- **THEN** the heartbeat reports an unsuccessful cycle with a reason, metrics remain committed, and other scheduled work continues
- **AND** another attempt is eligible after 300 seconds while still in the same eligible post-close day

#### Scenario: Successful capture and session boundaries
- **WHEN** capture succeeds or the clock is before 16:10 New York time or on a weekend
- **THEN** the scheduler does not start another post-close cycle for the completed day or outside its existing window
- **AND** missed historical sessions are not backfilled
