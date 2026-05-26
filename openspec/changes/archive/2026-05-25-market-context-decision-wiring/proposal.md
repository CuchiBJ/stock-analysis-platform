## Why

The `MarketContextEngine` shipped in `market-context-engine-phase-1` produces
rich, multi-dimensional descriptors (participation + leadership) but they
appear only as a status bar at the top of the dashboard. Nothing in the
ranking, filtering, or surfacing layers consumes them. The operator can see
`leadership EXHAUSTED` on the bar while the system continues to surface the
same setups it would surface under `leadership HEALTHY` — the platform
silently contradicts its own context engine.

This violates non-negotiable Principle 5 (**regime affects everything — same
metric scores differently per regime**). Today the descriptor is observation
only; this change makes it a decision filter.

The change is also the first concrete cross-engine consumer wired into the
workflow, proving the architecture before the five deferred MarketContextEngine
dimensions (persistence, forgiveness, rotation, volatility, follow_through)
arrive — they will plug into the same filter once shipped.

## What Changes

- New backend service `context_decision_filter.py` exposing
  `compute_context_multiplier(participation, leadership) → ContextMultiplier`
  with three outputs: `score_multiplier: float`, `suppress_lenses: list[str]`,
  `surface_warnings: list[str]`.
- Conservative Phase 1 rules:
  - `participation=COLLAPSING` → multiplier 0.5, suppress `[u-and-r, emerging-leaders]`
  - `participation=NARROWING` + leadership in `{THINNING, COLLAPSING, EXHAUSTED}` → multiplier 0.7, suppress `[emerging-leaders]`
  - `leadership=EXHAUSTED` (override) → multiplier 0.6, add warning `leadership_exhausted`
  - `participation=EXPANDING` + leadership in `{EXPANDING, HEALTHY}` → multiplier 1.1
  - `STABLE` / `UNKNOWN` / cold-start → multiplier 1.0, no suppression
  - `building-bases` lens NEVER suppressed (long-term construction is regime-independent)
- **BREAKING (additive)**: Setup queue endpoints (`/u-and-r`, `/emerging-leaders`, `/building-bases`) gain `suppressed: bool`, `suppression_reason: string | null`, and `context_snapshot: {participation, leadership}` fields in every response.
- Actionable setups endpoint (`/transitions/actionable`) gains `context_warnings: list[str]` per setup and applies `score_multiplier` to `priority_score` server-side.
- Frontend queue pages render a clear suppression card (not an empty state) when `suppressed: true`, with a "view anyway" UI-only override toggle.
- `MarketContextBar` surfaces a small "suprime N lenses" indicator that on hover lists affected lenses — operator can correlate bar state with downstream behavior.
- `CompactSetupCard` accepts optional `contextWarnings?: string[]` prop and renders an amber `leadership exhausted` badge when present.
- Suppression events log at INFO level with the descriptor pair, for operator visibility into why a queue is empty.
- New `/guide` section: "Cómo el contexto filtra los setups".

## Capabilities

### New Capabilities

- `context-decision-filter`: Centralized rules that translate market context descriptor pairs into actionable filtering decisions (score multipliers, lens suppression, surfaced warnings). Single source of truth for "how context affects the workflow."

### Modified Capabilities

- `setup-lifecycle`: Actionable setups response now exposes server-applied `score_multiplier` and per-setup `context_warnings` — `priority_score` is contextual, not raw. (No new requirements for state detection itself; only the response contract changes.)

## Non-goals

- **NOT** validating suppression thresholds against `transition_observations` history — deferred to August 2026 recalibration alongside descriptor thresholds.
- **NOT** wiring `participation` into `EmpiricalProbabilityCalculator.lookup()` — the calculator accepts the parameter but Phase 1 still skips Level 1 cohort. This change does not activate that path.
- **NOT** per-symbol context overrides (e.g., "specific leader survives COLLAPSING") — Phase 1 rules operate at lens granularity only.
- **NOT** an operator-configurable rules UI — rules are code constants.
- **NOT** rebalancing existing `priority_score` weight components — only multiplying the final score.
- **NOT** telemetry of suppression frequency — informal operator feedback drives any future tuning.
- **NOT** persistence / forgiveness / rotation / volatility / follow_through engines — those remain in `engines_pending`.
- **NOT** a backend `?override_suppression=true` flag — override is UI-only so the backend always tells the truth.

## Impact

**New code:**
- `backend/app/services/context_decision_filter.py` (~150 LOC, well under 400 LOC decomposition threshold)

**Modified backend:**
- `backend/app/api/v1/endpoints/transitions.py` — `/actionable` endpoint
- `backend/app/api/v1/endpoints/queue.py` — three lens endpoints

**Modified frontend:**
- `frontend/components/dashboard/MarketContextBar.tsx` — suppression indicator
- `frontend/components/dashboard/TopActionableSetups.tsx` — pass-through `context_warnings`
- `frontend/components/dashboard/CompactSetupCard.tsx` — `contextWarnings` prop + badge
- `frontend/app/queue/*/page.tsx` — handle `suppressed: true` response
- `frontend/app/guide/page.tsx` — new section

**API contract:**
- Additive fields on three queue endpoints and the actionable endpoint
- External consumers (curl, future mobile) must check `suppressed` flag — documented contract change

**Performance:**
- One additional context fetch per request to the four affected endpoints; cached in `context_decision_filter` (5-min TTL) and the underlying `MarketContextEngine` (also cached). Negligible overhead.

**No DB changes. No migrations. No new dependencies.**
