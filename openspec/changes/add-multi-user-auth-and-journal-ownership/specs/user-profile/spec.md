## ADDED Requirements

### Requirement: Every account has one minimal profile
The system SHALL create exactly one profile for every registered or bootstrapped account. The profile SHALL contain the stable user identifier, a display name of 1 to 80 trimmed characters, and timestamps; email, role, verification state, and lifecycle state SHALL remain server-controlled account fields.

**Implementation:** `backend/app/models/user.py`, `backend/app/services/profile_service.py`

#### Scenario: Registration creates a profile atomically
- **WHEN** a registration transaction succeeds
- **THEN** the user and its single profile both exist, or neither exists if the transaction fails

#### Scenario: Administrator bootstrap creates a profile
- **WHEN** the administrator account is created by the bootstrap operation
- **THEN** a profile linked to that administrator is created in the same operation

### Requirement: Authenticated user can view and edit only their profile
The system SHALL let an authenticated active user retrieve their account/profile summary and update their own display name. It MUST derive the target user from the session, MUST NOT accept another user ID as an authorization selector, and MUST NOT allow the profile update to alter email, role, verification state, or lifecycle state.

**Implementation:** `backend/app/api/v1/endpoints/profile.py`, `backend/app/services/profile_service.py`, `frontend/app/profile/page.tsx`

#### Scenario: User updates their display name
- **GIVEN** an authenticated active user
- **WHEN** the user submits a valid new display name
- **THEN** only that user's profile is updated and the session/account menu reflects the new value

#### Scenario: User submits privileged fields
- **WHEN** a profile update contains role, status, email, verification, or another user's identifier
- **THEN** the system rejects or ignores those fields without changing any privileged account data

### Requirement: Application navigation exposes current identity and logout
The authenticated application layout SHALL show a compact account control containing the current display name and SHALL provide access to profile editing and logout without displacing the primary trading workflow.

**Implementation:** `frontend/components/layout/DashboardLayout.tsx`, `frontend/components/auth/AccountMenu.tsx`

#### Scenario: Authenticated layout is rendered
- **GIVEN** an authenticated session with a profile
- **WHEN** any protected application page is rendered
- **THEN** the account control identifies the current user and offers profile and logout actions

#### Scenario: Session becomes invalid during navigation
- **WHEN** the current-session request returns `401`
- **THEN** the layout removes private user state and routes to login instead of rendering a stale identity
