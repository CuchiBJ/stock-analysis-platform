## ADDED Requirements

### Requirement: Every journal trade has exactly one owner
Every `journal_trades` row SHALL reference one existing user through a non-null owner identifier. New manual trades, partial-close rows, CSV-imported trades, and broker-synchronized trades MUST inherit the authenticated user's identifier, and decision-parent relationships MUST NOT cross owner boundaries.

**Implementation:** `backend/app/models/stock.py`, `backend/app/repositories/journal_repository.py`, `backend/alembic/versions/*_add_journal_ownership.py`

#### Scenario: User creates a trade
- **GIVEN** an authenticated user
- **WHEN** the user creates a manual journal trade or takes a trade from the queue
- **THEN** the new trade belongs to that user regardless of any owner field supplied by the client

#### Scenario: User partially closes a trade
- **GIVEN** a user-owned open trade
- **WHEN** the owner records a partial close
- **THEN** the closed child retains the same owner and its decision parent belongs to that owner

#### Scenario: Persistence attempts a cross-owner decision link
- **WHEN** a trade would reference a parent trade owned by another user
- **THEN** the operation is rejected and no cross-owner relationship is committed

### Requirement: All journal reads and aggregates are owner-scoped
The journal trade list, open positions, decision groups, statistics, stop history, CSV export, and every journal-derived count SHALL use only trades owned by the authenticated user. Shared market observations MAY inform a user's journal calculations but MUST NOT make another user's trade or outcome discoverable.

**Implementation:** `backend/app/repositories/journal_repository.py`, `backend/app/services/journal_service.py`, `backend/app/api/v1/endpoints/journal.py`

#### Scenario: Two users have journal entries
- **GIVEN** Alice and Bob each own trades
- **WHEN** Alice requests trades, statistics, decisions, stop history, or CSV export
- **THEN** every returned row and aggregate is computed only from Alice's trades

#### Scenario: User has no trades
- **GIVEN** an authenticated user with an empty journal while other users have trades
- **WHEN** the user opens the journal
- **THEN** the system returns an empty journal and zero/empty metrics without revealing that other trades exist

### Requirement: Journal mutations authorize by owner and conceal foreign identifiers
Edit, close, delete, stop-history mutation/read, regime backfill, and other trade-specific operations SHALL resolve resources by both trade ID and authenticated owner. A missing ID and an ID owned by another user MUST produce the same `404` behavior and MUST NOT mutate data.

**Implementation:** `backend/app/repositories/journal_repository.py`, `backend/app/api/v1/endpoints/journal.py`

#### Scenario: Owner changes their trade
- **GIVEN** a trade belongs to the authenticated user
- **WHEN** the user edits, closes, or deletes it
- **THEN** the requested mutation applies only to that trade and its owner remains unchanged

#### Scenario: User guesses another user's trade ID
- **GIVEN** a trade belongs to a different user
- **WHEN** the authenticated caller requests its details, stop history, edit, close, or delete action
- **THEN** the system responds as if the trade did not exist and leaves it unchanged

### Requirement: CSV import replacement is isolated to the caller
Journal CSV import SHALL assign all created rows to the authenticated user. When `replace=true`, the operation SHALL remove and replace only that user's journal rows and dependent stop events; it MUST NOT delete, regroup, or recalculate another user's data.

**Implementation:** `backend/app/services/journal_importer.py`, `backend/app/repositories/journal_repository.py`

#### Scenario: User replaces their journal
- **GIVEN** Alice and Bob both have journal data
- **WHEN** Alice imports a CSV with replacement enabled
- **THEN** Alice's prior journal is replaced by Alice-owned imported rows and Bob's trades, stop events, and metrics remain unchanged

#### Scenario: Import fails validation
- **WHEN** an authenticated user's CSV cannot be parsed or persisted completely
- **THEN** the import transaction is rolled back and the user's pre-import journal remains intact

### Requirement: Broker execution idempotency is per owner
For non-null broker execution identifiers, the system SHALL enforce uniqueness on `(owner_user_id, broker_exec_id)` rather than globally. Re-importing an execution for one user MUST remain idempotent while a different user MAY own the same broker execution identifier.

**Implementation:** `backend/app/models/stock.py`, `backend/alembic/versions/*_add_journal_ownership.py`, broker synchronization service when enabled

#### Scenario: Same user imports the same execution twice
- **WHEN** one user synchronizes an already recorded broker execution identifier
- **THEN** the system updates or skips the existing owned record and creates no duplicate for that user

#### Scenario: Different users share an execution identifier
- **WHEN** two users independently import the same non-null broker execution identifier
- **THEN** each user may have one isolated trade with that identifier

### Requirement: Legacy journal data is assigned intact to the administrator
The system SHALL provide an idempotent, transactional migration operation that assigns every journal trade lacking an owner to one explicitly selected verified administrator. It MUST preserve trade IDs, field values, decision links, stop-event links, linked observations, row counts, and open/closed status, and it MUST abort if null-owned rows are mixed with rows belonging to a different account.

**Implementation:** `backend/scripts/claim_legacy_journal.py`, `backend/alembic/versions/*_add_journal_ownership.py`, `docs/ORACLE_DEPLOY.md`

#### Scenario: Existing production journal is claimed
- **GIVEN** a verified backup, an explicit administrator account, and only legacy null-owned trades
- **WHEN** the operator runs the claim operation
- **THEN** all existing trades belong to that administrator and pre/post validation reports matching identities, relationships, counts, and representative aggregates

#### Scenario: Claim target or ownership state is ambiguous
- **WHEN** the administrator email is absent, non-admin, duplicated, or legacy rows coexist with rows owned by another account
- **THEN** the operation aborts without partial ownership changes

#### Scenario: Claim operation is rerun
- **GIVEN** all legacy rows were already assigned to the selected administrator
- **WHEN** the same operation is run again
- **THEN** it reports zero rows requiring assignment and changes no journal data

### Requirement: User-specific journal browser state does not cross sessions
Private journal query caches, drafts, and locally stored preferences SHALL be partitioned by current user ID or removed at logout. The existing account-balance browser value MUST NOT be visible to a different user who later signs in with the same browser profile.

**Implementation:** `frontend/app/providers.tsx`, `frontend/app/journal/TradeForms.tsx`, `frontend/lib/api-client.ts`

#### Scenario: Two users share one browser
- **GIVEN** Alice used the journal and then logged out
- **WHEN** Bob logs in using the same browser profile
- **THEN** Bob sees none of Alice's cached trades, drafts, account balance, statistics, or profile data

### Requirement: Shared analysis remains global and read-only with respect to ownership
Market prices, stock metrics, queues, calibration observations, regime data, and scheduler outputs SHALL remain shared system data. Creating a user or journal trade MUST NOT duplicate these datasets, and a user's trade MAY reference a shared transition observation without granting access to another user's journal.

**Implementation:** `backend/app/models/stock.py`, `backend/app/services/journal_snapshot_service.py`

#### Scenario: Two users journal the same symbol and date
- **WHEN** two users create trades that link to the same shared transition observation
- **THEN** both private trades may retain that shared reference while neither user can discover the other's trade
