# invalidation-engine

## Purpose

Eliminate low-quality setups **before** they reach scoring or ranking.
Invalidation-first is the central pipeline pattern: detect bad setups first,
then look for good ones (Principle 4 — Deterioration is first-class
information). The target is 80–90% rejection rate; only 10–20% of candidates
should reach the priority engine.

## Scope

**In scope:**
- The 11 invalidation reasons and their detection rules
- The `InvalidationResult` contract (valid / reasons / confidence)
- Batch filtering of symbol lists against latest metrics
- Confidence scoring based on number of triggers

**Out of scope:**
- Ranking among valid setups (see [priority-engine](../priority-engine/spec.md))
- State detection (see [setup-lifecycle](../setup-lifecycle/spec.md))
- Regime-aware threshold variation (currently a deviation — see end of spec)

## Requirements

### Requirement: The System SHALL Recognize 11 Invalidation Reasons

Every rejection is labeled with at least one of these reasons. Labels feed
the audit log and the user-facing "why was this rejected" explanation.

**Implementation:** `backend/app/services/setup_invalidation_engine.py:14-26`

| Reason                       | Trigger condition (current implementation)                          |
|------------------------------|---------------------------------------------------------------------|
| SLOPPY_PULLBACK              | `weekly_volatility_contraction < 0.1` OR `weekly_tightness < 0.2`   |
| EXCESSIVE_VOLATILITY         | `adr_percent > 12.0`                                                |
| FAILED_RECLAIM_STRUCTURE     | `pullback_quality_score < 40` AND `-5 ≤ distance_to_ema21 ≤ 5`      |
| RS_DETERIORATION             | `relative_strength_spy < 90`                                        |
| SECTOR_WEAKNESS              | (Not implemented — requires sector-level RS tracking)               |
| HEAVY_SELLING                | `relative_volume > 3.0` AND `pullback_quality_score < 30`           |
| WIDE_WEEKLY_BARS             | `weekly_tightness < 0.15`                                           |
| FAILED_CONTINUATION          | `pullback_quality_score < 45` AND `distance_to_ema21 < -5`          |
| LOOSE_STRUCTURE              | `distance_to_ema21 < -20` OR `distance_to_ema50 < -15`              |
| ABNORMAL_DOWNSIDE_VOLUME     | `relative_volume > 4.0` AND `pullback_quality_score < 25`           |
| INSUFFICIENT_LIQUIDITY       | `avg_volume_10d IS NULL` OR `avg_volume_10d < 700_000`              |

Note: SECTOR_WEAKNESS is declared but not implemented; it is a known gap.

#### Scenario: Multiple reasons accumulate

- **Given** a stock with `relative_strength_spy = 85`, `adr_percent = 13.0`,
  and `avg_volume_10d = 300_000`
- **When** `check_setup_validity(metrics)` is called
- **Then** the result SHALL have `is_valid = false`
- **And** `invalidation_reasons` SHALL contain RS_DETERIORATION,
  EXCESSIVE_VOLATILITY, and INSUFFICIENT_LIQUIDITY

---

### Requirement: Validity Check SHALL Return a Structured Result

`check_setup_validity(metrics)` SHALL return `InvalidationResult` with:
- `is_valid: bool` — true iff zero reasons triggered
- `invalidation_reasons: List[InvalidationReason]`
- `confidence: float` in [0, 1]

**Implementation:** `setup_invalidation_engine.py:29-106`

#### Scenario: Clean setup returns is_valid = true with empty reasons

- **Given** a stock that passes all 11 checks
- **When** `check_setup_validity(metrics)` is called
- **Then** `is_valid` SHALL be `true`
- **And** `invalidation_reasons` SHALL be `[]`
- **And** `confidence` SHALL be `1.0`

#### Scenario: Confidence decreases linearly with rejection count

- **Given** a stock that triggers 3 invalidation reasons
- **When** `check_setup_validity(metrics)` is called
- **Then** `confidence` SHALL equal `max(0.0, 1.0 - 3 × 0.1) = 0.7`

#### Scenario: Confidence floored at 0

- **Given** a stock that triggers all 11 reasons
- **When** `check_setup_validity(metrics)` is called
- **Then** `confidence` SHALL equal `0.0` (not negative)

---

### Requirement: INSUFFICIENT_LIQUIDITY SHALL Reject Setups with Volume < 700k

The liquidity floor for setups is `avg_volume_10d >= 700_000`. This is
stricter than the universe-level `QUALITY_FILTERS` floor of 500k —
universe inclusion is necessary but not sufficient for being a tradeable setup.

**Rationale:** Execution slippage on a 500k–700k volume stock at institutional
size is unacceptable. The 700k floor is the operational threshold.

**Implementation:** `setup_invalidation_engine.py:337-350`

#### Scenario: NULL volume is treated as insufficient

- **Given** `avg_volume_10d IS NULL`
- **When** `_is_insufficient_liquidity(metrics)` is called
- **Then** the result SHALL be `true`

#### Scenario: 600k volume is rejected

- **Given** `avg_volume_10d = 600_000`
- **When** `_is_insufficient_liquidity(metrics)` is called
- **Then** the result SHALL be `true`

#### Scenario: 800k volume passes liquidity

- **Given** `avg_volume_10d = 800_000`
- **When** `_is_insufficient_liquidity(metrics)` is called
- **Then** the result SHALL be `false`

---

### Requirement: Batch Filter SHALL Skip Symbols Without Metrics

`filter_valid_setups(symbols, limit)` SHALL:
1. Look up latest `StockMetrics` row for each symbol (order by date desc, limit 1)
2. Skip symbols with no metrics row (without raising)
3. Run `check_setup_validity` on each metric
4. Stop once `limit` valid symbols are collected

**Implementation:** `setup_invalidation_engine.py:108-148`

#### Scenario: Symbol without metrics is silently skipped

- **Given** symbol "ZZZZ" has no row in `stock_metrics`
- **When** `filter_valid_setups(["ZZZZ", "AAPL"], 50)` is called
- **Then** the result SHALL be `["AAPL"]` if AAPL is valid
- **And** the function SHALL NOT raise

#### Scenario: Limit short-circuits the loop

- **Given** the first 5 symbols are all valid and `limit = 5`
- **When** `filter_valid_setups(symbols, 5)` is called
- **Then** the function SHALL stop after collecting 5 valid symbols
- **And** SHALL NOT process the remaining symbols

#### Scenario: Per-symbol exception does not break the batch

- **Given** symbol "BAD" raises during metrics lookup
- **When** `filter_valid_setups(["BAD", "AAPL"], 50)` is called
- **Then** the error SHALL be logged
- **And** AAPL SHALL still be evaluated

---

### Requirement: Invalidation SHALL Run Before Scoring in the Pipeline

The canonical pipeline order is:
1. Universe quality filter ([universe-management](../universe-management/spec.md))
2. **Invalidation** (this capability)
3. State detection ([setup-lifecycle](../setup-lifecycle/spec.md))
4. Priority scoring ([priority-engine](../priority-engine/spec.md))

Skipping invalidation or running it after scoring defeats Principle 4
(deterioration first-class) and lets noise reach the user.

#### Scenario: A stock failing invalidation never receives a priority score

- **Given** stock XYZ triggers `RS_DETERIORATION`
- **When** the scanning pipeline runs end-to-end
- **Then** XYZ SHALL NOT appear in any priority ranking
- **And** XYZ SHALL NOT have a `priority_score` computed against it

---

### Requirement: Thresholds SHALL Eventually Vary by Regime

Current implementation uses fixed thresholds in all regimes. The
PRODUCT_BRAIN `INVALIDATION_ENGINE.md` specifies regime-aware thresholds
(stricter in bear/volatile, looser in bull). This is a known deviation tracked
for a future change.

Target after change:
- `risk_on`: thresholds as current (baseline)
- `transition` / `choppy`: stricter by ~15%
- `risk_off`: stricter by ~30% (e.g. RS_DETERIORATION fires at RS < 95, not < 90)

#### Scenario: After change, RS_DETERIORATION fires earlier in risk_off

- **Given** the regime-aware change is implemented
- **And** a stock has `relative_strength_spy = 92`
- **When** the regime is `risk_off`
- **Then** `_is_rs_deterioration(metrics, regime="risk_off")` SHALL return `true`
- **And** in `risk_on` the same call SHALL return `false`
