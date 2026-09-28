## 1. Identity persistence and dependencies

- [x] 1.1 [user-authentication] Add maintained Argon2id/password-hashing and token/security dependencies with pinned compatible versions.
- [x] 1.2 [user-authentication] Add SQLAlchemy models for users, auth sessions, email-verification tokens, and password-reset tokens with UUID identities, normalized unique email, roles, states, expiries, and digest-only tokens.
- [x] 1.3 [user-profile] Add the one-to-one user profile model with display-name validation and created/updated timestamps.
- [x] 1.4 [user-authentication] Create the expand Alembic migration for identity tables and indexes, including reversible schema-only downgrade behavior.
- [x] 1.5 [user-authentication] Add unit tests for email normalization, account-state transitions, password hashing/verification, token hashing, expiry, and single-use semantics.

## 2. Authentication core and session security

- [x] 2.1 [user-authentication] Implement cryptographic token generation, digest comparison, password policy, Argon2id hashing, and constant-shape authentication failures in a dedicated auth service.
- [x] 2.2 [user-authentication] Implement server-side session creation, lookup, 30-day absolute expiry, current-session revocation, and all-session revocation.
- [x] 2.3 [user-authentication] Implement `get_current_user` and active-account dependencies with secure cookie parsing and no anonymous fallback.
- [x] 2.4 [user-authentication] Implement per-session CSRF issuance/validation and trusted-origin checks for authentication mutations.
- [x] 2.5 [user-authentication] Add Redis-backed rate limits for registration, login, verification resend, and recovery by source plus normalized email.
- [x] 2.6 [user-authentication] Add security tests for invalid/expired/revoked sessions, disabled users, missing/invalid CSRF, hostile origins, and rate-limit enforcement.

## 3. Registration, verification, login, and recovery APIs

- [x] 3.1 [user-authentication] Define the mailer interface plus development capture adapter without logging raw verification/reset tokens.
- [x] 3.2 [user-authentication] Implement the SMTP adapter and validate required production mail/public-base-URL configuration at startup.
- [x] 3.3 [user-authentication] Implement transactional registration that creates a `user` role account and profile and sends a 24-hour verification link.
- [x] 3.4 [user-authentication] Implement email verification and rate-limited verification resend with invalidation of older outstanding tokens.
- [x] 3.5 [user-authentication] Implement login, current-session, and logout endpoints with the secure host-only cookie and CSRF response contract.
- [x] 3.6 [user-authentication] Implement non-enumerating forgot/reset-password endpoints with 60-minute single-use tokens and all-session revocation.
- [x] 3.7 [user-authentication] Add API tests for successful and rejected registration, verification, login/logout, duplicate email, self-assigned role input, and password recovery.

## 4. Administrator bootstrap and account profile

- [x] 4.1 [user-authentication] Implement an idempotent non-echoing administrator bootstrap CLI that creates or validates one verified active admin and profile.
- [x] 4.2 [user-authentication] Implement a server-side emergency password-reset CLI for the selected administrator without printing secrets.
- [x] 4.3 [user-profile] Implement current-profile retrieval and display-name update services that derive identity only from the session.
- [x] 4.4 [user-profile] Add `/api/v1/profile` read/update endpoints with allow-listed fields and 1–80 character trimmed display-name validation.
- [x] 4.5 [user-profile] Add tests proving users cannot update another profile or alter email, role, verification, or lifecycle state through profile input.

## 5. Journal ownership schema and migration tooling

- [x] 5.1 [journal-ownership] Add nullable `owner_user_id` to `JournalTrade`, owner-leading indexes, and model relationships in the expand migration.
- [x] 5.2 [journal-ownership] Replace global broker execution uniqueness with non-null per-owner `(owner_user_id, broker_exec_id)` uniqueness and test both same-owner and cross-owner cases.
- [x] 5.3 [journal-ownership] Validate existing stop-event references and add a real trade foreign key with appropriate cascade cleanup where validation succeeds.
- [x] 5.4 [journal-ownership] Implement the idempotent `claim_legacy_journal` dry-run/execute CLI with explicit admin lookup, transaction locking, ambiguous-state aborts, and token/data-safe count output.
- [x] 5.5 [journal-ownership] Add pre/post migration validators for trade IDs/counts, open/closed counts, field checksums, decision-parent targets, stop-event targets, links, and representative aggregates.
- [x] 5.6 [journal-ownership] Create the contract migration that enforces non-null ownership and final foreign keys only after the claim validators pass.
- [x] 5.7 [journal-ownership] Add migration tests for fresh database, legacy claim, idempotent rerun, mixed-owner abort, and integrity-preserving failure rollback.

## 6. Owner-scoped journal backend

- [x] 6.1 [journal-ownership] Introduce a journal repository whose public methods all require `owner_user_id` and provide no unscoped list/get/delete fallback.
- [x] 6.2 [journal-ownership] Move journal aggregate/decision orchestration into an owner-scoped service while retaining pure calculation helpers.
- [x] 6.3 [journal-ownership] Refactor trade listing, stats, export, open counts, linked counts, and decision grouping to consume only repository-scoped rows.
- [x] 6.4 [journal-ownership] Refactor create, edit, close, partial close, delete, and stop-history lookups to resolve `(trade_id, owner_user_id)` and return indistinguishable `404` results for foreign IDs.
- [x] 6.5 [journal-ownership] Update manual creation, queue-to-trade drafts/actions, decision assignment, and partial-close children to copy the authenticated owner and prevent cross-owner parent links.
- [x] 6.6 [journal-ownership] Refactor `JournalImporter` to require an owner, make import transactional, and limit `replace=true` plus dependent cleanup to that owner.
- [x] 6.7 [journal-ownership] Scope regime backfill and any broker synchronization/idempotency paths to the authenticated owner while leaving market snapshots shared.
- [x] 6.8 [journal-ownership] Reduce the journal endpoint module to thin authenticated routes and add a static/code-review guard that flags direct unscoped `JournalTrade` queries outside approved migration/maintenance modules.

## 7. Route and transport protection

- [x] 7.1 [user-authentication] Register auth/profile routers and apply active-user authentication to every API router except explicit auth and health endpoints.
- [x] 7.2 [user-authentication] Require session authentication during protected WebSocket handshakes and test rejection before streaming data.
- [x] 7.3 [user-authentication] Configure credentialed requests only for exact trusted HTTPS origins and preserve unauthenticated Caddy/container health checks.
- [x] 7.4 [user-authentication] Add endpoint inventory tests that fail when a new product API route is registered without the authentication dependency or an explicit public exemption.

## 8. Frontend authentication and profile experience

- [x] 8.1 [user-authentication] Build one shared credentialed API client that attaches CSRF proof to mutations and handles `401` session loss centrally.
- [x] 8.2 [user-authentication] Add the session provider and protected-route middleware/layout with safe same-origin return-path handling.
- [x] 8.3 [user-authentication] Build registration and verification/resend pages with generic, non-enumerating completion states.
- [x] 8.4 [user-authentication] Build login, forgot-password, and reset-password pages with accessible validation and session establishment.
- [x] 8.5 [user-profile] Build the profile page and compact account menu showing display name, profile navigation, and logout.
- [x] 8.6 [user-authentication] Update dashboard, journal, queue, calibration, chat, guide, and stock pages/components to use the shared API client instead of ad hoc authentication-unaware fetches.
- [x] 8.7 [journal-ownership] Make authenticated CSV export work on the canonical same origin without placing session secrets in the URL or JavaScript.
- [x] 8.8 [journal-ownership] Partition private TanStack Query keys and journal local-storage values by user ID and clear/cancel them on logout or invalid session.
- [x] 8.9 [user-authentication] Add frontend tests for route redirects, auth forms, session loss, logout cleanup, and rejection of unsafe return URLs.
- [x] 8.10 [journal-ownership] Add a shared-browser test proving a second user cannot see the first user's cached trades, account balance, drafts, stats, or profile.

## 9. Deployment and operational readiness

- [x] 9.1 [user-authentication] Add session, CSRF, trusted-origin, public-base-URL, SMTP, and cookie configuration to examples and Docker Compose without committing secrets.
- [x] 9.2 [user-authentication] Update the OCI runbook with mail DNS prerequisites, admin bootstrap, emergency reset, public-registration enablement, and auth-aware rollback steps.
- [x] 9.3 [journal-ownership] Update backup/restore and deploy procedures for the expand/bootstrap/claim/validate/contract maintenance window.
- [x] 9.4 [journal-ownership] Rehearse the migration against a restored production backup and save a redacted validation report demonstrating preservation of the administrator's journal.
- [x] 9.5 [user-authentication] Add token-free structured security events and operational checks for auth failure rates, mail failures, and session creation/revocation.

## 10. Verification

- [x] 10.1 [user-authentication] Run backend unit/integration tests and verify password/token/session/CSRF/rate-limit/auth-route coverage passes with no secret-bearing logs.
- [x] 10.2 [journal-ownership] Run an adversarial two-user API matrix across list, stats, export, import/replace, create, edit, close, delete, stop history, backfill, queue-to-trade, and broker IDs; verify all foreign-ID attempts return `404` and make zero changes.
- [x] 10.3 [journal-ownership] Compare pre/post migration counts, IDs, relationships, open/closed positions, and representative statistics on the restored production dataset, then test a full restore from backup.
- [x] 10.4 [user-profile] Verify registration creates exactly one profile, profile edits are owner-only, privileged fields remain immutable, and the account menu updates correctly.
- [x] 10.5 [user-authentication] Run frontend lint/typecheck/build plus browser smoke tests over HTTPS for register, verify, login, recovery, protected navigation, profile, logout, and session expiry.
- [x] 10.6 [journal-ownership] Perform the final release verification: admin sees every historical operation unchanged, a newly registered user starts with an empty journal, each user can independently import/create/manage/export trades, and neither can observe the other's private data.

## 11. Administrator-only production mode

- [x] 11.1 [user-authentication] Add explicit fail-closed configuration that permits production without SMTP only when public account flows and mail delivery are disabled.
- [x] 11.2 [user-authentication] Reject disabled registration/verification/recovery endpoints before mutation and expose login as the sole public account page in administrator-only builds.
- [x] 11.3 [user-authentication] Update Compose, environment examples, provisioning, and the OCI runbook for administrator-only deployment with later SMTP enablement.
- [x] 11.4 [user-authentication] Add backend/frontend coverage and run static, build, and focused authentication verification.
