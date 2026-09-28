## Context

The production stack is self-hosted on OCI behind Caddy. Caddy routes `/api/*` to FastAPI and all browser pages to Next.js on the same HTTPS origin; PostgreSQL and Redis are private Docker services. The backend currently has a placeholder API-key dependency that always succeeds, the frontend has no session provider, and every journal endpoint operates on the entire `journal_trades` table. `JournalTrade` also uses globally unique broker execution IDs, and the journal UI stores account balance under one unscoped browser key.

The database restored to OCI already contains the administrator's historical journal. The migration therefore cannot treat existing rows as test data or delete/re-import them. Trade IDs, `parent_trade_id` decision groups, `journal_stop_events.trade_id`, linked transition observations, snapshots, and calculated outcomes must survive unchanged.

This is a cross-cutting security boundary. The design covers browser authentication, backend authorization, persistence, migration, deployment, and every journal access path. It also requires decomposing `backend/app/api/v1/endpoints/journal.py`, which is over 1,300 lines, so ownership enforcement is centralized and reviewable.

## Goals / Non-Goals

**Goals:**

- Allow any person to register, verify an email address, sign in, sign out, recover access, and maintain a minimal profile.
- Establish a server-controlled identity and role for every request without exposing credentials or reusable session secrets to JavaScript.
- Require authentication for the product UI and API while retaining unauthenticated liveness/readiness health checks.
- Make journal data private to its owner across reads, writes, aggregates, imports, exports, stop histories, backfills, decision grouping, and UI caches.
- Create an administrator account and transfer all legacy journal rows to it without changing journal semantics or history.
- Keep market data and system-generated analysis shared, so authentication does not multiply ingestion or compute workloads.
- Provide isolation and migration tests strong enough to block deployment on a tenant-boundary regression.

**Non-Goals:**

- User-specific stock scores, stock selection, or dashboard-menu personalization.
- OAuth/social identity, teams, shared journals, delegated access, billing, or an admin data-browser UI.
- Letting the administrator implicitly read or mutate another user's journal.
- Email-address change, self-service account deletion, or multi-factor authentication in this iteration.
- Replacing OCI, PostgreSQL, Caddy, FastAPI, or Next.js with a managed identity/platform service.

## Decisions

### 1. FastAPI and PostgreSQL own identity; sessions are opaque and server-side

Add `users`, `user_profiles`, `auth_sessions`, `email_verification_tokens`, and `password_reset_tokens`. User IDs are UUIDs; email is trimmed and case-normalized into a unique canonical value. Registration always creates role `user`; only the bootstrap command can create or promote the initial `admin`. Account states are `pending_verification`, `active`, and `disabled`.

Passwords are hashed with Argon2id through a maintained password-hashing library. Opaque session and action tokens contain at least 256 bits of randomness; only SHA-256 token digests are stored. A session has a 30-day absolute lifetime, is revoked on logout, and all sessions are revoked after password reset or account disablement.

The browser receives the session in an `HttpOnly`, `Secure`, `SameSite=Lax`, host-only cookie. State-changing requests also carry a per-session CSRF token in `X-CSRF-Token`; login, registration, verification, and recovery endpoints enforce trusted `Origin` values and rate limits through Redis. Authentication errors use generic messages where account enumeration would otherwise be possible.

This keeps the security boundary in the existing backend and supports immediate revocation. Stateless JWTs were rejected because they complicate logout, password-reset revocation, and emergency account disablement. An external identity provider was rejected for this phase because the deployment is already self-contained and the required flow is limited to email/password.

### 2. Email verification and recovery use expiring one-time tokens behind an adapter

Registration sends a verification link whose token expires after 24 hours. Password-recovery requests send a reset link whose token expires after 60 minutes. Tokens are single-use, stored only as digests, and a newly issued token invalidates older outstanding tokens of the same type. The administrator bootstrap marks its known email as verified.

Define a small mailer interface with an SMTP production adapter and a capture/log-safe development adapter; production refuses to start public auth if required mail settings are absent. This avoids coupling account logic to one email vendor while still making the public flow complete. Deferring all verification/recovery was rejected because it leaves public accounts unrecoverable and allows email-address squatting.

Production also supports an explicit administrator-only mode for installations without a sender domain. In that mode the mailer is `disabled`, registration, verification, resend, and password-recovery/reset endpoints fail closed before mutation, and the frontend exposes login only. The bootstrapped verified administrator remains recoverable through the non-echoing server-side reset CLI. Public account flows cannot be enabled until production has complete encrypted SMTP configuration.

### 3. Authentication is enforced once at router/layout boundaries

FastAPI exposes `/api/v1/auth/*` and `/api/v1/profile`. Every `/api/v1/*` route other than registration/login/verification/recovery and explicit health endpoints depends on `get_current_user`; protected WebSocket connections authenticate during the handshake. Caddy continues to expose root `/health` without auth for container and load-balancer checks.

Next.js adds public `/login`, `/register`, `/verify-email`, and `/forgot-password`/`reset-password` pages plus an authenticated application layout. A session provider loads `/api/v1/auth/session`; unauthenticated navigation is redirected to login with a safe local return path. A shared API client sends credentials and the CSRF header, handles `401` centrally, and prevents ad hoc fetch behavior from drifting between journal screens.

All user pages are private even though most market data remains logically shared. This protects paid API-derived output and makes the browser experience predictable. Per-endpoint public/private decisions were rejected as unnecessarily ambiguous for the first public release.

### 4. Ownership is explicit on the journal root and inherited by child records

Add non-null `journal_trades.owner_user_id -> users.id` and owner-leading indexes used by listing, statistics, symbol grouping, open-position counts, and imports. `journal_stop_events` remains owned through its trade; add a real foreign key with cascade cleanup if existing data validation allows it. Decision grouping and partial closes copy the owner's UUID, and no parent/child decision group may span owners.

All journal repository/service entry points require `owner_user_id`; there is no optional owner parameter and no unscoped fallback. Resource lookup uses `(id, owner_user_id)`, returning `404` for missing and foreign resources. `replace=true` imports delete and replace only the caller's journal and its dependent stop events. Statistics, CSV export, regime backfill, trade drafts that create records, and broker synchronization all use the caller's owner scope.

Change the broker idempotency constraint from unique `broker_exec_id` to unique `(owner_user_id, broker_exec_id)` for non-null execution IDs. Market snapshots and `transition_observations` remain shared reference data and may be linked from multiple users' private trades without revealing either user's data.

Database row-level security was considered as defense in depth but rejected for this iteration because the application and scheduler currently share one PostgreSQL role and introducing transaction-local tenant state would enlarge deployment risk. Mandatory repository signatures, composite lookups, constraints, and adversarial integration tests form the initial boundary; PostgreSQL RLS remains a future hardening option.

### 5. Journal code is decomposed around an owner-scoped service

Split authentication-neutral metric helpers from HTTP routing and introduce an owner-scoped journal repository/service. Suggested boundaries are:

- `backend/app/api/v1/endpoints/auth.py` and `profile.py` for identity APIs.
- `backend/app/api/v1/endpoints/journal.py` as thin request/response routing.
- `backend/app/repositories/journal_repository.py` for mandatory owner-filtered persistence.
- Existing journal import, decision, and snapshot services updated to accept explicit owner context.

This is required because adding dozens of inline `where owner_id = ...` clauses to the current endpoint file would be hard to audit and easy to miss. The pure outcome/aggregation helpers remain reusable but receive only an already-scoped trade collection.

### 6. Browser state and query caches are partitioned by identity

TanStack Query keys that can contain private data include the current user ID. Logout cancels requests, clears private query data, clears user-scoped journal drafts/preferences, and then revokes the session. The journal account-balance local-storage key becomes user-scoped (or moves to an explicitly user-owned profile preference); a new user on the same browser cannot inherit the preceding user's value.

CSV export remains same-origin so the session cookie applies to the download. Frontend error handling treats `401` as session loss and `403` only as an authenticated account-state/CSRF problem; foreign trade identifiers still produce `404`.

### 7. Legacy ownership is a staged, counted migration

Use an expand/backfill/contract sequence rather than guessing an owner inside a schema migration:

1. Back up PostgreSQL and record counts/checksums for trades, stop events, decision links, and open/closed totals.
2. Apply the expand migration: identity tables, nullable `owner_user_id`, supporting indexes, and the new composite broker constraint.
3. Run an idempotent administrator bootstrap CLI with an explicit normalized email and password supplied through a non-echoing prompt; it creates or validates one verified active admin account.
4. Run an idempotent claim CLI with that exact admin email. In one transaction it locks journal writes, assigns every null-owned legacy trade to the admin, and aborts if any row already belongs to a different account or integrity checks fail.
5. Validate row counts, `parent_trade_id` targets, stop-event targets, broker identifiers, and representative journal statistics against the pre-migration report.
6. Apply the contract migration making `owner_user_id` non-null and enabling final foreign keys/indexes, then deploy the auth-aware API/frontend.

The claim command supports `--dry-run` and emits counts, never journal contents. Fresh installations bootstrap the admin before accepting registrations. If validation fails before the contract step, roll back the claim transaction and old code remains compatible. After contract/deployment, application rollback requires an auth-aware prior release; database restoration from the verified pre-migration backup is the destructive last resort.

## Risks / Trade-offs

- [Missed unscoped query leaks another user's journal] → Route journal access through a mandatory owner-scoped repository, prohibit direct `JournalTrade` queries outside approved modules, and add two-user tests for every read/write endpoint.
- [Legacy journal is assigned to the wrong account] → Require an explicit pre-created admin email, dry-run counts, transactional claim, invariant checks, operator confirmation, and a tested backup restore.
- [Authentication locks out the administrator] → Bootstrap a verified admin before contract migration, validate login before public DNS cutover, and document a server-side password-reset command.
- [Session theft] → Use high-entropy opaque tokens, digest-only storage, secure host-only cookies, TLS, expiry/revocation, password-reset revocation, and no token logging.
- [CSRF or credential stuffing] → Require CSRF tokens and trusted origins, keep `SameSite=Lax`, and rate-limit registration/login/recovery by IP plus normalized email without revealing account existence.
- [Email provider outage blocks onboarding/recovery] → Keep mail delivery behind an adapter, surface safe retry states, support verification resend limits, and monitor delivery failures without logging tokens.
- [User-specific data remains in the browser after logout] → Partition query/local-storage state by user and clear it before completing logout.
- [Single database role lacks RLS defense in depth] → Treat application scoping as a release-blocking invariant and revisit RLS after tenant-aware database roles/transaction context are designed.

## Migration Plan

1. Rehearse the complete expand/bootstrap/claim/contract flow against a restored production backup and save the validation report.
2. Configure session, CSRF, trusted-origin, and public-base-URL settings. Choose administrator-only mode with disabled mail, or configure encrypted SMTP before enabling public account flows; confirm secrets are excluded from source control and logs.
3. Put the journal into a maintenance window, take an off-host-capable backup, and execute the staged migration described above.
4. Deploy API and frontend together, then verify admin login and historical counts before reopening registration.
5. Run two-account isolation, registration/verification, recovery, profile, import/export, create/edit/close/delete, and logout cache-clearing smoke tests over HTTPS.
6. Monitor authentication failures, mail delivery, session creation, and journal authorization errors without recording passwords, tokens, or journal payloads.

Rollback before the contract migration is transaction rollback plus the prior application. Rollback after contract migration uses an auth-aware application release; if data integrity is suspect, stop writes and restore the verified backup rather than attempting a lossy down migration.

## Open Questions

- Which SMTP service and sender domain will be used if public accounts are enabled later? Administrator-only mode does not require one.
- What final public hostname replaces the temporary `sslip.io` address? Cookie host scope and verification/reset links require a stable HTTPS base URL before launch.
