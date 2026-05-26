# setup-lifecycle

## Purpose

Define the operational state model for a momentum setup. Unlike a generic
Emerging→Active→Deteriorating lifecycle, this system is **pre-reclaim
focused**: the operational edge is born in compression/flush/tightening
phases *before* the textbook reclaim signal. Losing an EMA is not automatically
bearish — it is often the beginning of the next setup.

## Scope

**In scope:**
- The 11 lifecycle states and their detection rules
- Detection priority order (deterioration first, then continuation, then reclaim, then pre-reclaim)
- State transition detection (current vs prior state)
- Per-state narrative generation
- Continuation probability calculation

**Out of scope:**
- Operational transition strength (`OperationalTransition`) — see [transition-engine](../transition-engine/spec.md)
- Ranking among valid setups — see [priority-engine](../priority-engine/spec.md)
- Rejecting setups for low quality — see [invalidation-engine](../invalidation-engine/spec.md)
- Regime detection — see [market-regime](../market-regime/spec.md)

## Requirements

### Requirement: The System SHALL Recognize Exactly 11 Lifecycle States

States are partitioned into four groups: pre-reclaim (operational focus),
reclaim (exist but not focus), continuation, and deterioration.

**Implementation:** `backend/app/services/setup_lifecycle_engine.py:22-56`

| Group         | State                  | Operational meaning                                |
|---------------|------------------------|----------------------------------------------------|
| Pre-reclaim   | EARLY_PULLBACK         | First EMA loss, structure intact, monitor          |
| Pre-reclaim   | CONTROLLED_PULLBACK    | Orderly 1–3.5 ATR below EMA21, EMA50 healthy       |
| Pre-reclaim   | VOLATILITY_CONTRACTION | ATR compressing actively below EMAs                |
| Pre-reclaim   | TIGHTENING             | Multiple tight weeks + volume contraction          |
| Pre-reclaim   | UNDERCUT               | Constructive EMA50 flush + volume spike            |
| Pre-reclaim   | SUPPORT_TESTING        | Testing EMA50 zone with EMA21 already lost         |
| Reclaim       | RECLAIM_PREPARATION    | -1.0 to -0.5 ATR below EMA21 + pullback_score ≥ 65 |
| Reclaim       | RECLAIM_IN_PROGRESS    | -0.5 to -0.05 ATR below EMA21 (late entry)         |
| Continuation  | CONTINUATION           | 0 to +1.5 ATR above EMA21 + weekly_trend > 0.7     |
| Deterioration | DISTRIBUTION           | EMA21 lost + volume expanding + RS collapsing      |
| Deterioration | BROKEN                 | distance_to_ema50_atr < -2.5                       |

#### Scenario: Each metrics row maps to exactly one state

- **Given** a `StockMetrics` row with all required fields
- **When** `detect_current_state(metrics)` is called
- **Then** it SHALL return exactly one `SetupState` enum value
- **And** the returned value SHALL be one of the 11 defined states

---

### Requirement: Detection SHALL Follow the Documented Priority Order

State detection runs in priority order. The first matching condition wins.
Deterioration is checked first so a broken structure is never mislabeled as a
constructive pullback.

**Order** (implementation: `setup_lifecycle_engine.py:82-116`):
1. BROKEN
2. DISTRIBUTION
3. CONTINUATION
4. RECLAIM_IN_PROGRESS
5. RECLAIM_PREPARATION
6. UNDERCUT
7. SUPPORT_TESTING
8. TIGHTENING
9. VOLATILITY_CONTRACTION
10. CONTROLLED_PULLBACK
11. EARLY_PULLBACK (default)

#### Scenario: BROKEN beats UNDERCUT when both could match

- **Given** `distance_to_ema50_atr = -2.8` and `relative_volume = 1.5`
- **When** state detection runs
- **Then** the result SHALL be `BROKEN`, not `UNDERCUT`

#### Scenario: DISTRIBUTION beats EARLY_PULLBACK

- **Given** `distance_to_ema21_atr = -1.0`, `relative_volume = 1.5`, `relative_strength_spy = 90`
- **When** state detection runs
- **Then** the result SHALL be `DISTRIBUTION` (all three deterioration triggers met)

---

### Requirement: BROKEN Detection SHALL Use ATR-Normalized Distance to EMA50

`BROKEN` is defined exclusively by `distance_to_ema50_atr < -2.5`. Raw
percentage distances SHALL NOT be used.

**Implementation:** `setup_lifecycle_engine.py:191-194`

#### Scenario: BROKEN trips at -2.6 ATR

- **Given** `distance_to_ema50_atr = -2.6`
- **When** `_is_broken(metrics)` is called
- **Then** it SHALL return `true`

#### Scenario: NULL ATR distance does not trigger BROKEN

- **Given** `distance_to_ema50_atr IS NULL`
- **When** `_is_broken(metrics)` is called
- **Then** it SHALL return `false` (no false positive on missing data)

---

### Requirement: DISTRIBUTION SHALL Require Three Simultaneous Conditions

DISTRIBUTION is the most aggressive deterioration label. It SHALL require ALL
three of:
- `distance_to_ema21_atr < -0.8` (EMA21 lost)
- `relative_volume > 1.3` (volume expanding)
- `relative_strength_spy < 95` (RS collapsing)

A single condition is not enough — that would generate false alarms during
healthy pullbacks.

**Implementation:** `setup_lifecycle_engine.py:196-205`

#### Scenario: Two of three conditions is not DISTRIBUTION

- **Given** EMA21 lost and volume expanding, but `relative_strength_spy = 110`
- **When** state detection runs
- **Then** the state SHALL NOT be `DISTRIBUTION`

---

### Requirement: Continuation Probability SHALL Be a Weighted Composite

`calculate_continuation_probability(metrics)` SHALL return a value in [0, 1]
combining the following components:

| Component              | Weight | Source field                  |
|------------------------|--------|-------------------------------|
| Weekly trend quality   | 40%    | `weekly_trend_quality`        |
| Pullback quality score | 30%    | `pullback_quality_score / 100`|
| Relative strength      | 20%    | `relative_strength_spy` (tiered) |
| Volume contraction     | 10%    | `volume_contraction`          |

RS tiering:
- ≥ 115: +0.20
- ≥ 110: +0.16
- ≥ 105: +0.12
- ≥ 100: +0.08
- ≥ 95:  +0.04
- < 95:  +0.00

**Implementation:** `setup_lifecycle_engine.py:136-165`

#### Scenario: Strong setup gets high probability

- **Given** `weekly_trend_quality = 0.9`, `pullback_quality_score = 90`,
  `relative_strength_spy = 115`, `volume_contraction = 0.8`
- **When** `calculate_continuation_probability` is called
- **Then** the result SHALL be > 0.85

#### Scenario: Missing fields SHALL contribute 0, not error

- **Given** `relative_strength_spy IS NULL`
- **When** `calculate_continuation_probability` is called
- **Then** the function SHALL NOT raise
- **And** the RS component SHALL contribute 0 to the total

---

### Requirement: Each State SHALL Have a Short Operational Narrative

`generate_narrative(metrics, state)` SHALL return a single-sentence string
describing the operational meaning of the state. Narratives SHALL be
context-compressed (Principle 3) — no raw metric dumps.

**Implementation:** `setup_lifecycle_engine.py:167-187`

#### Scenario: Narrative is non-empty for every state

- **Given** any `SetupState` value
- **When** `generate_narrative(metrics, state)` is called
- **Then** the result SHALL be a non-empty string
- **And** the string SHALL fit on one line (no newlines)

---

### Requirement: State Transitions SHALL Be Detected and Logged

When a stock's state changes between two consecutive evaluations,
`detect_state_transition(symbol, old_state, new_state)` SHALL return a
`StateTransition` object and log the change. If the state has not changed, it
SHALL return `None`.

**Implementation:** `setup_lifecycle_engine.py:118-134`

#### Scenario: Same state returns None

- **Given** `old_state == new_state == TIGHTENING`
- **When** `detect_state_transition("AAPL", old_state, new_state)` is called
- **Then** the result SHALL be `None`
- **And** nothing SHALL be logged at INFO level

#### Scenario: Transition is logged at INFO

- **Given** old state is `CONTROLLED_PULLBACK` and new state is `TIGHTENING`
- **When** `detect_state_transition("AAPL", old_state, new_state)` is called
- **Then** a `StateTransition` object SHALL be returned
- **And** an INFO log SHALL include `AAPL` and both state names
