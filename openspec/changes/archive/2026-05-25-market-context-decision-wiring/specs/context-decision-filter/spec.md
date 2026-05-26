## ADDED Requirements

### Requirement: Context Decision Filter SHALL Translate Descriptor Pairs to Actionable Decisions

The system SHALL expose a `context_decision_filter.compute_context_multiplier(participation, leadership)` function that returns a `ContextMultiplier` value object with exactly three fields:

- `score_multiplier: float` in the range `[0.0, 2.0]`
- `suppress_lenses: list[str]` containing zero or more of `{"u-and-r", "emerging-leaders", "building-bases"}`
- `surface_warnings: list[str]` containing zero or more warning identifiers

The function SHALL be pure (no side effects) and idempotent for a given input pair.

The participation parameter SHALL accept the values `EXPANDING`, `STABLE`, `NARROWING`, `COLLAPSING`, `UNKNOWN`. The leadership parameter SHALL accept the values `EXPANDING`, `HEALTHY`, `THINNING`, `COLLAPSING`, `EXHAUSTED`, `UNKNOWN`. Any other value SHALL be treated as `UNKNOWN` without raising.

#### Scenario: Default neutral multiplier for benign combinations

- **GIVEN** `participation = "STABLE"` and `leadership = "HEALTHY"`
- **WHEN** `compute_context_multiplier(participation, leadership)` is called
- **THEN** the result SHALL be `ContextMultiplier(score_multiplier=1.0, suppress_lenses=[], surface_warnings=[])`

#### Scenario: Unknown descriptors are neutral, never suppressive

- **GIVEN** `participation = "UNKNOWN"` and `leadership = "EXHAUSTED"`
- **WHEN** `compute_context_multiplier(participation, leadership)` is called
- **THEN** the result SHALL have `score_multiplier = 1.0`
- **AND** `suppress_lenses` SHALL be empty
- **AND** `surface_warnings` SHALL be empty

#### Scenario: Invalid descriptor values are treated as UNKNOWN

- **GIVEN** `participation = "NOT_A_REAL_VALUE"` and `leadership = "HEALTHY"`
- **WHEN** `compute_context_multiplier(participation, leadership)` is called
- **THEN** no exception SHALL be raised
- **AND** the result SHALL have `score_multiplier = 1.0` and `suppress_lenses = []`

---

### Requirement: COLLAPSING Participation SHALL Trigger Strong Suppression

When `participation = "COLLAPSING"`, the multiplier SHALL be `0.5` and the lenses `["u-and-r", "emerging-leaders"]` SHALL be suppressed, regardless of leadership state. The `building-bases` lens SHALL NOT be suppressed by participation state.

#### Scenario: COLLAPSING participation suppresses short-horizon lenses

- **GIVEN** `participation = "COLLAPSING"` and `leadership = "HEALTHY"`
- **WHEN** the multiplier is computed
- **THEN** `score_multiplier` SHALL be `0.5`
- **AND** `suppress_lenses` SHALL equal `["u-and-r", "emerging-leaders"]`
- **AND** `"building-bases"` SHALL NOT appear in `suppress_lenses`

---

### Requirement: NARROWING + Adverse Leadership SHALL Suppress Emerging-Leaders

When `participation = "NARROWING"` and `leadership` is one of `{"THINNING", "COLLAPSING", "EXHAUSTED"}`, the multiplier SHALL be `0.7` and the `emerging-leaders` lens SHALL be suppressed. U&R SHALL remain available because established leaders may still set up.

#### Scenario: NARROWING + THINNING suppresses emerging only

- **GIVEN** `participation = "NARROWING"` and `leadership = "THINNING"`
- **WHEN** the multiplier is computed
- **THEN** `score_multiplier` SHALL be `0.7`
- **AND** `suppress_lenses` SHALL equal `["emerging-leaders"]`
- **AND** `"u-and-r"` SHALL NOT appear in `suppress_lenses`

#### Scenario: NARROWING + healthy leadership does not suppress

- **GIVEN** `participation = "NARROWING"` and `leadership = "HEALTHY"`
- **WHEN** the multiplier is computed
- **THEN** `suppress_lenses` SHALL be empty

---

### Requirement: EXHAUSTED Leadership SHALL Add Warning to Surviving Setups

When `leadership = "EXHAUSTED"` and the combination is not already covered by a stronger rule, the multiplier SHALL be `0.6` and `surface_warnings` SHALL contain the identifier `"leadership_exhausted"`. This warning is the contract surface for the frontend amber badge.

#### Scenario: EXHAUSTED leadership warning is emitted

- **GIVEN** `participation = "STABLE"` and `leadership = "EXHAUSTED"`
- **WHEN** the multiplier is computed
- **THEN** `score_multiplier` SHALL be `0.6`
- **AND** `"leadership_exhausted"` SHALL be in `surface_warnings`

#### Scenario: COLLAPSING participation rule wins over EXHAUSTED leadership

- **GIVEN** `participation = "COLLAPSING"` and `leadership = "EXHAUSTED"`
- **WHEN** the multiplier is computed
- **THEN** `score_multiplier` SHALL be `0.5` (COLLAPSING rule takes precedence)
- **AND** `suppress_lenses` SHALL equal `["u-and-r", "emerging-leaders"]`

---

### Requirement: EXPANDING + Supportive Leadership SHALL Boost Scores

When `participation = "EXPANDING"` and `leadership` is one of `{"EXPANDING", "HEALTHY"}`, the multiplier SHALL be `1.1`. No lens SHALL be suppressed. The boost is intentionally modest — Phase 1 errs toward caution.

#### Scenario: EXPANDING + HEALTHY boosts modestly

- **GIVEN** `participation = "EXPANDING"` and `leadership = "HEALTHY"`
- **WHEN** the multiplier is computed
- **THEN** `score_multiplier` SHALL be `1.1`
- **AND** `suppress_lenses` SHALL be empty

---

### Requirement: Building-Bases Lens SHALL NEVER Be Suppressed

For any combination of `participation` and `leadership` values, the string `"building-bases"` SHALL NOT appear in `suppress_lenses`. Building-bases reflects multi-week structural formation and is regime-independent by construction.

#### Scenario: Worst-case combination does not suppress building-bases

- **GIVEN** `participation = "COLLAPSING"` and `leadership = "EXHAUSTED"`
- **WHEN** the multiplier is computed
- **THEN** `"building-bases"` SHALL NOT appear in `suppress_lenses`

---

### Requirement: Filter Result SHALL Be Cached With 5-Minute TTL

The filter SHALL maintain an in-process cache keyed by the `(participation, leadership)` tuple with a TTL of 300 seconds. Cache hits SHALL return the same `ContextMultiplier` reference without recomputation.

#### Scenario: Second call within TTL returns cached result

- **GIVEN** `compute_context_multiplier("STABLE", "HEALTHY")` was called at time T
- **WHEN** the same call is made at time `T + 60s`
- **THEN** the result SHALL be returned from cache without re-executing rule lookup

---

### Requirement: Suppression Decisions SHALL Be Logged at INFO

When a lens is suppressed in response to a real request (i.e., not during the pure `compute_context_multiplier` call but during endpoint integration), the system SHALL emit a single INFO-level log line containing the lens identifier, the participation value, and the leadership value.

#### Scenario: Suppression log line is emitted

- **GIVEN** a request to `/api/v1/queue/u-and-r` while `participation = "COLLAPSING"`
- **WHEN** the suppression decision is applied
- **THEN** a log line at INFO SHALL be written containing `lens=u-and-r`, `participation=COLLAPSING`, and the current leadership value

---

### Requirement: Queue Endpoints SHALL Return Structured Suppression Response

The endpoints `/api/v1/queue/u-and-r`, `/api/v1/queue/emerging-leaders`, and `/api/v1/queue/building-bases` SHALL include three additional fields in every response (suppressed or not):

- `suppressed: bool`
- `suppression_reason: string | null` — non-null only when `suppressed = true`
- `context_snapshot: {participation: string, leadership: string}`

When `suppressed = true`, the `results` field SHALL still contain the computed candidate list (so the frontend can implement a "view anyway" override against the same payload). The `suppression_reason` SHALL be a human-readable Spanish sentence explaining which descriptor combination caused the suppression.

#### Scenario: Suppressed lens response shape

- **GIVEN** `participation = "COLLAPSING"` and a request to `/api/v1/queue/u-and-r`
- **WHEN** the endpoint responds
- **THEN** the response SHALL contain `suppressed: true`
- **AND** `suppression_reason` SHALL be a non-empty string
- **AND** `context_snapshot` SHALL be `{"participation": "COLLAPSING", "leadership": <current_leadership>}`
- **AND** `results` SHALL be present (may be empty if there are also no candidates, but the field SHALL exist)

#### Scenario: Non-suppressed lens response includes the new fields

- **GIVEN** `participation = "STABLE"` and a request to `/api/v1/queue/u-and-r`
- **WHEN** the endpoint responds
- **THEN** the response SHALL contain `suppressed: false`
- **AND** `suppression_reason` SHALL be `null`
- **AND** `context_snapshot` SHALL still be present

---

### Requirement: Actionable Endpoint SHALL Apply Score Multiplier and Emit Warnings

The `/api/v1/transitions/actionable` endpoint SHALL fetch the current context once at the start of the request and:

1. Multiply each `priority_score` by `context_multiplier.score_multiplier` (capped at 1.0 via the existing min-clamp).
2. Attach the `surface_warnings` list as a new `context_warnings: list[str]` field on each returned setup.
3. Include a top-level `context_snapshot: {participation, leadership}` field in the response (the response is currently a list — this requires wrapping in an object, see scenario below).

#### Scenario: Actionable response wraps list with context envelope

- **WHEN** `/api/v1/transitions/actionable` is called
- **THEN** the response SHALL be an object with shape `{"context_snapshot": {...}, "setups": [...]}` where `setups` is the current list and each setup carries a `context_warnings: list[str]` field
- **AND** when `leadership = "EXHAUSTED"`, every setup in `setups` SHALL have `"leadership_exhausted"` in its `context_warnings`

#### Scenario: Score multiplier reduces priority_score under hostile regime

- **GIVEN** `participation = "NARROWING"` and `leadership = "THINNING"` (multiplier 0.7)
- **AND** a setup whose pre-multiplier priority score is `0.80`
- **WHEN** the endpoint responds
- **THEN** the setup's `priority_score` SHALL be `0.56` (0.80 × 0.7)

---

### Requirement: UNKNOWN Context SHALL Pass Through Unchanged

When the upstream `MarketContextEngine` returns `UNKNOWN` for either descriptor (cold-start, cache miss with no data, etc.), the affected endpoints SHALL:

- Apply `score_multiplier = 1.0` (no change to scores)
- Suppress no lenses
- Still include `context_snapshot` in the response so the operator sees the `UNKNOWN` state

#### Scenario: Cold-start UNKNOWN does not suppress

- **GIVEN** the context engine returns `participation = "UNKNOWN"` and `leadership = "UNKNOWN"`
- **WHEN** any of the four affected endpoints is called
- **THEN** `suppressed` SHALL be `false` (for queue endpoints) or no warnings SHALL be attached (for actionable)
- **AND** `context_snapshot` SHALL show the `UNKNOWN` values verbatim
