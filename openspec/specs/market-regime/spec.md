# market-regime

## Purpose

Detect the current market environment so every downstream signal can be
interpreted in context. Regime is the master variable — the same setup quality
score means very different things in `risk_on` vs `risk_off`. Ignoring regime
is fatal (Principle 5).

## Scope

**In scope:**
- The 4 regimes the system recognizes
- The 5 contributing factors used in detection
- The rule-based determination logic
- Confidence scoring
- Regime narrative summary

**Out of scope:**
- Applying regime to setup scoring — see [priority-engine](../priority-engine/spec.md)
- Regime-aware invalidation — see [invalidation-engine](../invalidation-engine/spec.md)
- Persisting regime history (currently in-memory only — flagged in audit)

## Requirements

### Requirement: The System SHALL Recognize Exactly 4 Regimes

Regimes are an enum, not a continuum. Every detection call returns one of:
`risk_on`, `risk_off`, `transition`, `choppy`.

**Implementation:** `backend/app/services/market_regime_engine.py:16-22`

| Regime      | Operational meaning                                            |
|-------------|----------------------------------------------------------------|
| risk_on     | Strong breadth + healthy leadership; continuation favored      |
| risk_off    | Weak breadth or poor leadership; defensive posture required    |
| transition  | Mixed signals between breadth and leadership; caution warranted|
| choppy      | Neutral breadth + neutral leadership; no clear edge            |

Note: this differs from the PRODUCT_BRAIN `Bull/Bear/Volatile` taxonomy. The
implemented taxonomy supersedes the PRODUCT_BRAIN doc — `transition` and
`choppy` are operationally distinct states the philosophy doc collapsed into
"Volatile".

#### Scenario: Detection always returns a known regime

- **Given** any state of the database (including empty)
- **When** `detect_regime()` is called
- **Then** the returned `regime` field SHALL be one of the four enum values
- **And** the function SHALL NOT raise

---

### Requirement: Regime Detection SHALL Use Five Contributing Factors

`MarketRegimeAnalysis` SHALL include all five factors with values in [0, 1]:

1. **Breadth quality** — % of stocks above EMA50 (70%) + % near 52w highs (30%)
2. **Leadership health** — % of leaders (pullback_quality ≥ 60) above EMA21 (70%) + % with RS ≥ 105 (30%)
3. **Speculative appetite** — average ADR% normalized: `(avg_adr - 1) / 4`, clamped to [0, 1]
4. **Sector expansion** — % of stocks with positive 1-week performance
5. **Pullback environment quality** — average `pullback_quality_score` / 100

All five SHALL use `QUALITY_FILTERS` ([universe-management](../universe-management/spec.md))
to exclude penny/illiquid stocks.

**Implementation:** `market_regime_engine.py:102-280`

#### Scenario: Empty database returns 0.5 defaults, not exception

- **Given** `stock_metrics` is empty
- **When** any factor calculation runs
- **Then** it SHALL return `0.5` (neutral default)
- **And** SHALL log an error if the underlying query failed

#### Scenario: All five factors populated

- **Given** a populated `stock_metrics` table
- **When** `detect_regime()` completes
- **Then** the `MarketRegimeAnalysis` result SHALL have all five factor fields
  in [0, 1]
- **And** `confidence` SHALL be in [0.5, 1.0]

---

### Requirement: Regime Determination SHALL Follow This Rule Order

The rule order matters — first match wins.

**Implementation:** `market_regime_engine.py:282-306`

1. **risk_on** ← `breadth_quality > 0.65 AND leadership_health > 0.65`
2. **risk_off** ← `breadth_quality < 0.40 OR leadership_health < 0.40`
3. **transition** ← `abs(breadth_quality - leadership_health) > 0.20`
4. **choppy** ← default (none of the above)

#### Scenario: Strong breadth + healthy leaders → risk_on

- **Given** `breadth_quality = 0.70` and `leadership_health = 0.72`
- **When** `_determine_regime(...)` is called
- **Then** the result SHALL be `MarketRegime.RISK_ON`

#### Scenario: Weak breadth alone → risk_off

- **Given** `breadth_quality = 0.30` and `leadership_health = 0.55`
- **When** `_determine_regime(...)` is called
- **Then** the result SHALL be `MarketRegime.RISK_OFF` (OR semantics)

#### Scenario: Divergent factors → transition, not choppy

- **Given** `breadth_quality = 0.60` and `leadership_health = 0.30`
- **When** `_determine_regime(...)` is called
- **Then** the result SHALL be `MarketRegime.RISK_OFF` (leadership < 0.40 triggers first)
- **And** transition is reserved for mid-range divergence

#### Scenario: All factors neutral → choppy

- **Given** `breadth_quality = 0.50` and `leadership_health = 0.55`
- **When** `_determine_regime(...)` is called
- **Then** the result SHALL be `MarketRegime.CHOPPY`

---

### Requirement: Regime Confidence SHALL Reflect Factor Alignment

Confidence is `1.0 - stddev(factors)` clamped to `[0.5, 1.0]`. Aligned factors
produce high confidence; divergent factors produce low confidence (floor 0.5).

**Implementation:** `market_regime_engine.py:308-328`

#### Scenario: Perfectly aligned factors yield high confidence

- **Given** breadth, leadership, and speculative appetite all equal `0.80`
- **When** `_calculate_confidence(...)` is called
- **Then** the result SHALL equal `1.0`

#### Scenario: Divergent factors yield floor confidence

- **Given** breadth = 0.20, leadership = 0.80, speculative = 0.50
- **When** `_calculate_confidence(...)` is called
- **Then** the result SHALL equal `0.5` (floor)

---

### Requirement: Regime Endpoint SHALL Refresh on Polling

The frontend `MarketRegimePanel` component SHALL poll the regime endpoint at
no longer than a 60-second interval. (Currently violated — see audit Priority 1.)
This is a regression the spec asserts forward-looking; the change to add polling
is tracked as a pending OpenSpec change.

#### Scenario: Frontend reflects regime change within 60s

- **Given** the backend regime flips from `risk_on` to `transition`
- **When** the frontend `MarketRegimePanel` is open
- **Then** the displayed regime SHALL update within 60 seconds without a manual refresh
