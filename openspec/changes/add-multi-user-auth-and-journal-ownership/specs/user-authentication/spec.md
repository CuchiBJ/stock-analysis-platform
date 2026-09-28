## ADDED Requirements

### Requirement: Public registration creates a non-privileged account
The system SHALL allow an unauthenticated person to register with a display name, normalized unique email address, and password. It MUST assign role `user` regardless of client input, store only a strong password hash, create the corresponding profile, and keep product access pending until the email address is verified.

**Implementation:** `backend/app/api/v1/endpoints/auth.py`, `backend/app/models/user.py`, `frontend/app/register/page.tsx`

#### Scenario: New email is registered
- **GIVEN** no account exists for the normalized email
- **WHEN** a visitor submits valid registration data
- **THEN** the system creates a pending-verification user and profile, sends a verification message, and does not expose password hashes or verification tokens in the response

#### Scenario: Duplicate email is submitted
- **GIVEN** an account already exists for an email ignoring case and surrounding whitespace
- **WHEN** registration is submitted with an equivalent email
- **THEN** the system returns a generic accepted or conflict-safe response that does not disclose sensitive account state and creates no duplicate user

#### Scenario: Client attempts to self-assign administrator
- **WHEN** registration includes a role or administrator field
- **THEN** the system ignores or rejects that field and the persisted role remains `user`

### Requirement: Email verification uses a bounded single-use token
The system SHALL require a one-time verification token before a registered user can access protected product routes. Verification tokens MUST be stored only as digests, expire within 24 hours, become unusable after successful verification, and be omitted from application logs.

**Implementation:** `backend/app/services/auth_service.py`, `backend/app/services/mailer.py`, `frontend/app/verify-email/page.tsx`

#### Scenario: Valid verification link is used
- **GIVEN** a pending account and an unexpired unused verification token
- **WHEN** the user opens the verification link
- **THEN** the account becomes active and that token cannot be used again

#### Scenario: Expired or reused verification link is used
- **WHEN** a verification token is expired, invalid, or already consumed
- **THEN** the system rejects it without activating an account and offers a rate-limited resend path

### Requirement: Login establishes a revocable server-side session
The system SHALL authenticate an active user by normalized email and password and establish an opaque server-side session with a maximum absolute lifetime of 30 days. The reusable session token MUST be delivered only in an `HttpOnly`, `Secure`, `SameSite=Lax`, host-only cookie and MUST be stored server-side only as a digest.

**Implementation:** `backend/app/api/v1/endpoints/auth.py`, `backend/app/core/auth.py`, `backend/app/models/user.py`, `frontend/app/login/page.tsx`

#### Scenario: Active user signs in successfully
- **GIVEN** an active account with valid credentials
- **WHEN** the user logs in over HTTPS
- **THEN** the system creates a revocable session, sets the secure cookie, and returns the minimum current-user session data

#### Scenario: Credentials or account state are invalid
- **WHEN** the email/password is incorrect or the account is pending or disabled
- **THEN** the system creates no session and returns a generic authentication failure that does not reveal which condition failed

### Requirement: Logout and password reset revoke sessions
The system SHALL revoke the current session on logout and SHALL revoke all sessions belonging to a user after a successful password reset or account disablement. The browser SHALL clear private cached state when logout succeeds or a session is found invalid.

**Implementation:** `backend/app/services/auth_service.py`, `frontend/app/providers.tsx`, `frontend/lib/api-client.ts`

#### Scenario: User logs out
- **GIVEN** an authenticated browser session
- **WHEN** the user selects logout
- **THEN** the server revokes the session, expires the cookie, and the browser removes private query and user-scoped local state before showing the login page

#### Scenario: Password is reset while another session exists
- **GIVEN** the user has two active sessions
- **WHEN** a valid password-reset flow sets a new password
- **THEN** both prior sessions become unusable and the user must log in with the new password

### Requirement: Password recovery is non-enumerating and time-bounded
The system SHALL accept password-recovery requests without revealing whether an email is registered. A reset token MUST be single-use, stored only as a digest, expire within 60 minutes, and permit setting a new valid password only for the associated active account.

**Implementation:** `backend/app/api/v1/endpoints/auth.py`, `backend/app/services/auth_service.py`, `frontend/app/forgot-password/page.tsx`, `frontend/app/reset-password/page.tsx`

#### Scenario: Recovery is requested
- **WHEN** a visitor submits any syntactically valid email to password recovery
- **THEN** the system returns the same generic response and, only for an eligible account, sends a reset message subject to rate limits

#### Scenario: Valid reset token is consumed
- **GIVEN** an unexpired unused reset token for an active account
- **WHEN** a compliant new password is submitted
- **THEN** the password hash changes, the token is consumed, and all existing sessions are revoked

### Requirement: Product routes and APIs require an authenticated active user
The system SHALL protect all product pages, API routes, and WebSocket connections except the authentication flow and explicitly designated health endpoints. An unauthenticated browser SHALL be directed to login with only a validated same-origin return path; an unauthenticated API request SHALL receive `401` without protected data.

**Implementation:** `backend/app/core/auth.py`, `backend/app/api/v1/api.py`, `frontend/middleware.ts`, `frontend/components/auth/AuthProvider.tsx`

#### Scenario: Anonymous visitor opens a product page
- **WHEN** an unauthenticated visitor requests `/dashboard`, `/queue`, `/calibration`, `/journal`, `/chat`, `/guide`, or `/stock/{symbol}`
- **THEN** the visitor is redirected to login and the application content is not rendered

#### Scenario: Anonymous caller requests protected API data
- **WHEN** a request without a valid session reaches a protected HTTP or WebSocket endpoint
- **THEN** access is rejected before the endpoint reads or streams protected data

#### Scenario: Health probe runs without a session
- **WHEN** infrastructure requests an explicitly public liveness or readiness endpoint
- **THEN** the endpoint remains available without exposing user or journal data

### Requirement: Cookie-authenticated mutations resist cross-site requests and brute force
The system MUST validate a per-session CSRF token on authenticated state-changing requests and MUST validate trusted origins on unauthenticated auth mutations. Registration, login, verification resend, and password recovery SHALL be rate-limited by source and normalized identifier using configurable limits.

**Implementation:** `backend/app/core/auth.py`, `backend/app/core/redis.py`, `frontend/lib/api-client.ts`

#### Scenario: Authenticated mutation omits CSRF proof
- **GIVEN** a valid session cookie
- **WHEN** a state-changing request omits or supplies an invalid CSRF token
- **THEN** the system rejects the request without applying a mutation

#### Scenario: Authentication attempts exceed configured limits
- **WHEN** a source or normalized email exceeds the configured authentication-attempt threshold
- **THEN** the system temporarily rejects further attempts and records a token-free security event

### Requirement: Administrator identity is created outside public registration
The system SHALL provide an idempotent server-side bootstrap operation that creates or validates exactly one known verified active administrator from an explicit email and a password entered through a non-echoing channel. Public requests MUST NOT create or promote administrators, and administrator role alone MUST NOT grant access to another user's journal.

**Implementation:** `backend/scripts/bootstrap_admin.py`, `docs/ORACLE_DEPLOY.md`

#### Scenario: Administrator is bootstrapped on a fresh database
- **WHEN** an operator runs the bootstrap command with a new normalized email
- **THEN** one verified active admin account and profile are created without printing the password or hash

#### Scenario: Bootstrap is rerun safely
- **GIVEN** the target administrator already exists with the expected role
- **WHEN** the same bootstrap command is rerun
- **THEN** it reports the existing identity and creates no duplicate account

### Requirement: Production may run in explicit administrator-only mode
The system SHALL support a production mode without SMTP only when public registration, verification, resend, and password-recovery/reset flows are explicitly disabled. Those endpoints MUST fail before creating accounts or tokens, the frontend SHALL expose login as the only public account page, and administrator password recovery SHALL remain available through the server-side CLI. Enabling public account flows in production MUST continue to require complete encrypted SMTP configuration.

**Implementation:** `backend/app/core/config.py`, `backend/app/api/v1/endpoints/auth.py`, `backend/app/services/mailer.py`, `frontend/lib/auth-navigation.ts`, `compose.production.yml`

#### Scenario: Administrator-only production starts without SMTP
- **GIVEN** a public HTTPS base URL, `AUTH_PUBLIC_ACCOUNT_FLOWS_ENABLED=false`, and `MAILER_BACKEND=disabled`
- **WHEN** the production application starts
- **THEN** login/session/logout remain available while mail configuration is not required

#### Scenario: Visitor attempts a disabled public account flow
- **GIVEN** administrator-only mode
- **WHEN** a visitor requests registration, verification, resend, forgot-password, or reset-password
- **THEN** the request is rejected before any account, token, or mail mutation and the frontend offers no navigation to that flow

#### Scenario: Public account mode is enabled without SMTP
- **GIVEN** production has public account flows enabled
- **WHEN** SMTP credentials or encrypted transport are incomplete
- **THEN** startup fails closed
