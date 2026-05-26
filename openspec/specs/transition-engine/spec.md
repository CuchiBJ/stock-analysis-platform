# transition-engine

## Purpose

Track *how* a setup is evolving, not just *what* state it is in. Transition
quality, velocity, and direction are first-class signals — Principle 1 says
transitions dominate over static states. A stock in `TIGHTENING` for 3 days
with compressing volume is operationally different from one stuck in
`TIGHTENING` for 18 days with no change.

## Scope

**In scope:**
- Operational transitions within a state (12 enum values)
- Transition strength classification (4 levels)
- Transition direction (progressive / regressive / lateral)
- Freshness tracking (5 freshness states based on days-in-state)
- State hierarchy ordering (worst → best)
- Comparing two consecutive `StockMetrics` rows to derive transition metrics

**Out of scope:**
- The state itself (see [setup-lifecycle](../setup-lifecycle/spec.md))
- Ranking based on transition (see [priority-engine](../priority-engine/spec.md))

## Requirements

### Requirement: The System SHALL Recognize 12 Operational Transitions

Operational transitions describe *movement within* a state, not state-to-state
moves. They are the leading signal — they appear before the state itself changes.

**Implementation:** `backend/app/services/transition_engine.py:31-66`

| Group         | Transition              | Operational meaning                                |
|---------------|-------------------------|----------------------------------------------------|
| Pre-reclaim   | ENTERING_PULLBACK       | First EMA9/21 loss, structure intact               |
| Pre-reclaim   | VOLUME_DRY_UP           | Volume contracting below EMAs (KEY signal)         |
| Pre-reclaim   | COMPRESSING             | ATR contracting below EMAs                         |
| Pre-reclaim   | FLUSH_AND_RECOVER       | Spike low + recovery (constructive undercut)       |
| Pre-reclaim   | SUPPORT_HOLDING         | Bounces in support zone, institutional defense     |
| Reclaim       | RECLAIMING              | Recovering EMA21 (late signal)                     |
| Continuation  | CONTINUATION_HOLDING    | Holding EMA21 with structure                       |
| Deterioration | WEAKENING               | RS down, structure deteriorating                   |
| Deterioration | DISTRIBUTION            | Volume expansion on down moves, RS collapses       |
| Deterioration | FAILING                 | EMA50 lost with volume                             |
| Neutral       | STABLE                  | No meaningful change                               |
| Neutral       | STABILIZING             | Volatility settling without direction              |

Pre-reclaim transitions SHALL be ranked first in any feed (Principle 1 — the
operational edge is in pre-reclaim).

#### Scenario: No prior data returns STABLE

- **Given** `previous_metrics IS None`
- **When** `calculate_operational_transition(symbol, current, None)` is called
- **Then** the result SHALL be `OperationalTransition.STABLE` with strength 0.5

---

### Requirement: Transition Strength SHALL Be a 4-Level Enum

Strength values: `WEAK`, `MODERATE`, `STRONG`, `VERY_STRONG`.

A `VERY_STRONG` transition implies higher institutional conviction and SHALL
contribute proportionally more to the priority score (see [priority-engine](../priority-engine/spec.md)).

**Implementation:** `transition_engine.py:16-22`

#### Scenario: Strength is monotonic with magnitude of change

- **Given** two transitions: A has RS change +1.5 and volume change +5%; B has
  RS change +8.0 and volume change +40%
- **When** strength is computed for both
- **Then** B SHALL be classified at the same or higher strength tier than A

---

### Requirement: Transition Direction SHALL Be Progressive, Regressive, or Lateral

Direction is computed from the `STATE_HIERARCHY` ordering:
- `BROKEN=0, DISTRIBUTION=1, EARLY_PULLBACK=2, CONTROLLED_PULLBACK=3, VOLATILITY_CONTRACTION/SUPPORT_TESTING/UNDERCUT=4, TIGHTENING=5, RECLAIM_PREPARATION=6, RECLAIM_IN_PROGRESS=7, CONTINUATION=8`

- **PROGRESSIVE** = `hierarchy(to_state) > hierarchy(from_state)`
- **REGRESSIVE** = `hierarchy(to_state) < hierarchy(from_state)`
- **LATERAL** = equal hierarchy value

**Implementation:** `transition_engine.py:145-157`

#### Scenario: Tightening → reclaim_preparation is progressive

- **Given** `from_state = TIGHTENING (5)` and `to_state = RECLAIM_PREPARATION (6)`
- **When** direction is computed
- **Then** the result SHALL be `PROGRESSIVE`

#### Scenario: Continuation → distribution is regressive

- **Given** `from_state = CONTINUATION (8)` and `to_state = DISTRIBUTION (1)`
- **When** direction is computed
- **Then** the result SHALL be `REGRESSIVE`

#### Scenario: Volatility_contraction ↔ support_testing is lateral

- **Given** both states share hierarchy value 4
- **When** direction is computed
- **Then** the result SHALL be `LATERAL`

---

### Requirement: Freshness SHALL Be Tracked in 5 Bands

Freshness reflects how long a stock has been in its current state. Stale setups
SHALL be visually de-prioritized — institutional setups resolve within days,
not weeks (Principle 2 — Scarcity is signal).

**Bands** (`transition_engine.py:69-76`):
- `FRESH` — 0–3 days
- `AGING` — 4–7 days
- `LATE_STAGE` — 8–14 days
- `STALE` — 15–19 days
- `EXTENDED` — 20+ days

#### Scenario: A setup in TIGHTENING for 2 days is FRESH

- **Given** the state has been `TIGHTENING` for 2 days
- **When** freshness is computed
- **Then** the result SHALL be `FreshnessState.FRESH`

#### Scenario: A setup in CONTINUATION for 25 days is EXTENDED

- **Given** the state has been `CONTINUATION` for 25 days
- **When** freshness is computed
- **Then** the result SHALL be `FreshnessState.EXTENDED`
- **And** the setup decay factor SHALL be > 0.5

---

### Requirement: Operational Transitions SHALL Generate a Narrative

Every `OperationalTransitionMetrics` result SHALL include a `narrative` field —
a single-line operational summary suitable for display. No raw metric dumps
(Principle 3 — Context compression mandatory).

**Implementation:** `transition_engine.py:104` (narrative field)

#### Scenario: Narrative present even when transition is STABLE

- **Given** no meaningful change between current and previous metrics
- **When** `calculate_operational_transition` is called
- **Then** the result SHALL have `transition = STABLE`
- **And** `narrative` SHALL be a non-empty string (e.g. "No previous data for comparison.")

---

### Requirement: Velocity SHALL Affect Urgency, Not Just Magnitude

A fast negative transition (1–3 days) is operationally distinct from a slow
negative transition (8+ days). Fast negatives SHALL trigger high-urgency alerts;
slow ones SHALL trigger monitor-level alerts.

This requirement is forward-looking — current implementation reports magnitude
and direction; urgency mapping is a pending change.

#### Scenario: Fast negative transition flagged as high urgency

- **Given** RS drops 8 points in 2 days with volume expanding
- **When** transition urgency is assigned (future)
- **Then** the urgency SHALL be `HIGH` or `CRITICAL`

#### Scenario: Slow negative transition flagged as monitor

- **Given** RS drops 8 points over 10 days with stable volume
- **When** transition urgency is assigned (future)
- **Then** the urgency SHALL be `MEDIUM` (monitor, not exit-now)
