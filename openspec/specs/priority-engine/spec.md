# priority-engine

## Purpose

Rank the surviving setups (those that passed [invalidation-engine](../invalidation-engine/spec.md))
and surface only the top 3–6. Scarcity is signal (Principle 2) — if everything
looks good, nothing is. The priority engine enforces the "top of top" filter
that makes the product an operating system rather than a screener.

## Scope

**In scope:**
- The 6-component weighted scoring model
- Score component definitions and weights
- Regime alignment matrix (state × regime → score)
- Top-N ranking with minimum score threshold
- Priority summary statistics (distribution, top setup, etc.)

**Out of scope:**
- Setup detection (see [setup-lifecycle](../setup-lifecycle/spec.md))
- Invalidation/quality gating (see [invalidation-engine](../invalidation-engine/spec.md))
- Regime detection (see [market-regime](../market-regime/spec.md))

## Requirements

### Requirement: Priority Score SHALL Combine 6 Weighted Components

The priority score is a weighted sum of six components, each scored 0–100:

| Component             | Weight | Source                                              |
|-----------------------|--------|-----------------------------------------------------|
| state_quality         | 30%    | Contextual readiness × state operational multiplier |
| transition_strength   | 25%    | `pullback_quality_score` (proxy — see below)        |
| weekly_structure      | 15%    | `weekly_trend_quality × 100`                        |
| rs_stability          | 10%    | `relative_strength_spy` (tiered 100/80/60/40/20)    |
| regime_alignment      | 10%    | Alignment matrix lookup (state × regime)            |
| pullback_quality      | 10%    | `pullback_quality_score`                            |

**Implementation:** `backend/app/services/setup_priority_engine.py:63-102`

#### Scenario: Score in [0, 100] always

- **Given** any `StockMetrics`, `SetupState`, and `market_regime`
- **When** `calculate_priority_score(...)` is called
- **Then** the returned `priority_score` SHALL be in [0, 100]

#### Scenario: Missing optional fields fall back to neutral

- **Given** `relative_strength_spy IS NULL`
- **When** `_calculate_rs_stability(metrics)` is called
- **Then** the component SHALL return `50.0` (neutral default)

---

### Requirement: state_quality SHALL Use Contextual Readiness × Operational Multiplier

`state_quality` SHALL NOT be a flat state-to-score mapping. It SHALL use the
`ContextualSetupEngine.calculate_readiness_score()` result multiplied by a
state-specific operational priority multiplier.

**Multipliers** (`setup_priority_engine.py:147-164`):

| State                  | Multiplier |
|------------------------|------------|
| TIGHTENING             | 1.20       |
| VOLATILITY_CONTRACTION | 1.15       |
| RECLAIM_PREPARATION    | 1.15       |
| SUPPORT_TESTING        | 1.10       |
| UNDERCUT               | 1.10       |
| CONTINUATION           | 1.10       |
| CONTROLLED_PULLBACK    | 1.05       |
| EARLY_PULLBACK         | 1.00       |
| RECLAIM_IN_PROGRESS    | 1.00       |
| DISTRIBUTION           | 0.70       |
| BROKEN                 | 0.40       |

TIGHTENING gets the highest multiplier — it is the pre-reclaim sweet spot
(Principle 1 — pre-reclaim is the operational focus).

#### Scenario: Same readiness, different state → different score

- **Given** two stocks with identical `ContextualSetupEngine` readiness = 70
- **And** stock A is in `TIGHTENING`, stock B is in `EARLY_PULLBACK`
- **When** `_calculate_state_quality` runs for both
- **Then** A's score SHALL equal `70 × 1.20 = 84`
- **And** B's score SHALL equal `70 × 1.00 = 70`
- **And** A SHALL outrank B

#### Scenario: BROKEN heavily penalized

- **Given** a stock in `BROKEN` with readiness = 80
- **When** `_calculate_state_quality` runs
- **Then** the score SHALL equal `80 × 0.40 = 32`

---

### Requirement: Regime Alignment SHALL Use the Documented Matrix

Each `(state, regime)` pair maps to a fixed alignment score 0–100. The matrix
is the source of truth — there is no derived calculation.

**Implementation:** `setup_priority_engine.py:237-272`

Key rows:
- `(RECLAIM_PREPARATION, risk_on) = 100`
- `(RECLAIM_PREPARATION, risk_off) = 25`
- `(CONTINUATION, risk_on) = 100`
- `(CONTINUATION, risk_off) = 20`
- `(BROKEN, *) = 0`
- `(DISTRIBUTION, *) ≤ 20`

#### Scenario: Same state, different regime → different alignment

- **Given** state = `CONTINUATION`
- **When** alignment is computed against `risk_on` then against `risk_off`
- **Then** the `risk_on` result SHALL be `100` and `risk_off` result SHALL be `20`

#### Scenario: Unknown regime returns neutral

- **Given** state = `TIGHTENING` and regime = `"unknown_value"`
- **When** `_calculate_regime_alignment` is called
- **Then** the result SHALL be `50.0`

#### Scenario: NULL regime returns neutral

- **Given** `market_regime IS None`
- **When** `_calculate_regime_alignment` is called
- **Then** the result SHALL be `50.0`

---

### Requirement: Ranking SHALL Cap at 6 and Enforce Minimum Score

`rank_setups(setups, limit, min_score)` SHALL:
1. Filter out any setup with `priority_score < min_score`
2. Sort survivors descending by `priority_score`
3. Return at most `limit` setups (default 6)

The default minimum score is currently `50.0`. The audit recommends raising it
to ≥ 70 to truly enforce Principle 2 (scarcity). This is a pending change.

**Implementation:** `setup_priority_engine.py:104-128`

#### Scenario: Empty result is valid

- **Given** no setup exceeds `min_score`
- **When** `rank_setups(setups, 6, 70.0)` is called
- **Then** the result SHALL be an empty list
- **And** the system SHALL display "no setups today" rather than relaxing filters

#### Scenario: Limit caps even when many qualify

- **Given** 50 setups exceed `min_score`
- **When** `rank_setups(setups, 6, 50.0)` is called
- **Then** the result SHALL have exactly 6 setups
- **And** they SHALL be the 6 highest priority_score values, sorted descending

---

### Requirement: Priority Result SHALL Include Full Breakdown

Every `SetupPriority` SHALL expose all six component scores plus the
contextual current_state. Interpretability is mandatory (Principle 7) — no
opaque score without breakdown.

**Implementation:** `setup_priority_engine.py:14-38`

#### Scenario: Breakdown contains every component

- **Given** a calculated `SetupPriority`
- **When** `setup.get_breakdown()` is called
- **Then** the dict SHALL contain keys: `symbol`, `priority_score`,
  `state_quality`, `transition_strength`, `weekly_structure`,
  `rs_stability`, `regime_alignment`, `pullback_quality`, `current_state`

---

### Requirement: Priority Summary SHALL Provide Aggregate Statistics

`get_priority_summary(ranked_setups)` SHALL return:
- `total_analyzed` / `total_passed_threshold`
- `avg_priority_score`
- `top_setup` (breakdown of #1)
- `state_distribution` (count by state)

**Implementation:** `setup_priority_engine.py:287-323`

#### Scenario: Empty input returns zero-stats, not exception

- **Given** an empty list of ranked setups
- **When** `get_priority_summary([])` is called
- **Then** the result SHALL have `total_analyzed = 0`, `avg_priority_score = 0.0`,
  `top_setup = None`, and `state_distribution = {}`
- **And** the function SHALL NOT raise

---

### Requirement: Regime SHALL Multiply, Not Just Weight 10%

Currently regime contributes 10% to the priority score as a weighted component.
The audit (Priority 2 item #7) flagged this as too weak: regime should act as
a **multiplier** on the final score, not a small additive term.

A future spec change SHALL replace the additive regime_alignment with a regime
multiplier in [0.5, 1.2] applied to the final score. This requirement marks
the constraint forward — current behavior is a known deviation.

#### Scenario: After change, risk_off cuts CONTINUATION scores

- **Given** the regime-multiplier change is implemented
- **And** a stock has raw priority_score = 80 in CONTINUATION
- **When** the regime is `risk_off`
- **Then** the final score SHALL be ≤ `80 × 0.6 = 48` (heavy haircut)

#### Scenario: After change, risk_on boosts TIGHTENING scores

- **Given** the regime-multiplier change is implemented
- **And** a stock has raw priority_score = 75 in TIGHTENING
- **When** the regime is `risk_on`
- **Then** the final score SHALL be in `[75, 75 × 1.2 = 90]`
