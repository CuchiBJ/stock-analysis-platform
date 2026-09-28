## Why

The cloud deployment currently exposes a single shared application state: there is no real user identity and every journal request reads or mutates the same `journal_trades` data. Before publishing the product broadly, the application needs secure self-service accounts and strict per-user journal ownership while preserving the administrator's existing journal history.

This change extends principle 6 (operational clarity over feature richness) and principle 10 (workflow over analytics): identity and data ownership become explicit foundations of the workflow instead of implicit deployment assumptions.

## What Changes

- Add public email-and-password registration, login, logout, persistent authenticated sessions, and a minimal account-recovery flow suitable for the public web deployment.
- Add a user account and profile model with a stable identifier, unique normalized email, display name, role (`user` or `admin`), lifecycle state, and timestamps.
- Protect application pages and private API operations; unauthenticated users are directed to authentication instead of receiving application or journal data.
- Make every journal trade belong to exactly one user and scope all journal reads, statistics, imports, exports, draft-to-trade actions, edits, closes, stop histories, backfills, and deletes to the authenticated owner.
- Preserve globally shared market data, scans, transition observations, and system-generated analysis; authentication does not duplicate those datasets per user.
- Add a one-time, auditable migration that creates the administrator account and assigns every pre-existing journal trade to it without changing trade identifiers, decision links, stop history, or analytical values.
- Change broker execution deduplication from global to per-user so separate users may legitimately import the same broker execution identifier.
- Add profile viewing/editing and an account menu that exposes the current identity and logout action.
- Decompose the journal endpoint module (currently over 1,300 lines) into authentication-aware dependencies/services or smaller routers as part of the work, so ownership checks are centralized rather than repeated inconsistently.
- **BREAKING**: journal API endpoints that are currently anonymous SHALL require an authenticated user, and existing unowned journal rows SHALL become invalid after the ownership migration is complete.

## Capabilities

### New Capabilities

- `user-authentication`: Public account registration, login/logout, session handling, password recovery, route/API protection, and role-aware account lifecycle.
- `user-profile`: Minimal per-user profile creation, retrieval, and editing, including administrator identity and account menu behavior.
- `journal-ownership`: Per-user ownership and isolation across the complete journal workflow, including safe adoption of legacy administrator data.

### Modified Capabilities

None. The current canonical specs do not define authentication, profiles, or journal ownership; these are introduced as new capabilities.

## Impact

- Backend: new user/profile persistence, password hashing and token/session infrastructure, authentication dependencies, journal query/mutation scoping, migration/backfill tooling, and authorization tests.
- Frontend: registration, login, password-recovery and profile surfaces; authenticated session provider/API client; protected layouts; account navigation; authenticated CSV export.
- Database: new user/profile/session or recovery-token tables, non-null journal owner foreign key, per-owner indexes/constraints, and an idempotent legacy-data assignment migration.
- Deployment: new authentication secrets and public-origin/cookie settings, HTTPS-only production cookies, and an administrator bootstrap procedure integrated with backup/restore and deploy runbooks.
- APIs: journal operations become authenticated and return only the caller's resources; cross-owner resource identifiers are treated as not found.
- Verification: automated tenant-isolation tests, migration rehearsal against a restored production backup, and public registration/login/profile/journal smoke tests.

## Non-goals

- Defining or implementing user-specific stock scoring criteria.
- Letting users choose which stocks appear on the main dashboard or changing the priority engine; that work belongs to a later OpenSpec change.
- Social login, organizations, teams, shared journals, subscriptions, billing, or paid-plan entitlements.
- An administrator console for browsing or editing other users' journal data.
- Per-user copies of market data, scanner results, queues, calibration data, or system analysis.
- Migrating the deployment away from the existing OCI, Docker Compose, PostgreSQL, Caddy, FastAPI, and Next.js architecture.
