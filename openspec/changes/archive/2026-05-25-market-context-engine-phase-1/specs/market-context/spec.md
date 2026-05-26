## ADDED Requirements

### Requirement: The System SHALL Produce Multi-Dimensional Market Context

The market context output SHALL be a vector of orthogonal behavior dimensions,
each independently meaningful. The system SHALL NOT collapse the vector into a
single label, a single composite score, or any other 1-dimensional summary.

The full framework defines seven dimensions: `participation`,
`leadership_quality`, `persistence`, `forgiveness`, `rotation`,
`volatility_behavior`, `follow_through`. Phase 1 implements `participation` and
`leadership_quality` and SHALL declare the remaining five as pending via an
`engines_pending` field in the response.

#### Scenario: Response shape is multi-dimensional, not labeled

- **WHEN** `GET /api/v1/market-context/current` is called against any
  non-empty database state
- **THEN** the response SHALL contain top-level keys `participation` and
  `leadership` populated with structured data
- **AND** the response SHALL contain a list `engines_pending` enumerating the
  five not-yet-implemented dimensions
- **AND** the response SHALL NOT contain any field named `regime`, `state`,
  `label`, or `verdict` that maps the full context to a single value

#### Scenario: No composite numeric score per engine

- **WHEN** the response is inspected
- **THEN** neither `participation` nor `leadership` SHALL contain a field
  named `score` or `composite_score` or equivalent
- **AND** each engine SHALL expose raw metrics + a qualitative descriptor
  string only

---

### Requirement: Leader Definition SHALL Be Minervini SEPA

The system SHALL define "leader" for the `leadership_quality` engine as `quality_leader_gate.is_quality_leader` (the 8-criteria Minervini SEPA gate), and SHALL NOT use `pullback_quality_score >= 60` or any other technical-only definition.

This requirement establishes a single source of truth for "leader" across
the platform. Any future engine, queue lens, or scoring module that needs
to identify leaders SHALL delegate to the same gate.

#### Scenario: Leader count uses Minervini gate

- **GIVEN** the latest `stock_metrics` snapshot
- **WHEN** `leadership_quality` is computed
- **THEN** `leader_count` SHALL equal the count of `StockMetrics` rows at
  that date passing `QUALITY_FILTERS` AND `is_quality_leader(m) == True`
- **AND** `leader_count` SHALL NOT be derived from `pullback_quality_score`
  thresholds

#### Scenario: Historical leader sets use the same gate

- **WHEN** `leader_count_delta_5d` is computed
- **THEN** the system SHALL apply `is_quality_leader` to the `stock_metrics`
  rows at `as_of - 7 calendar days` (~5 trading days)
- **AND** the comparison SHALL be set-based: turnover counts symbols joining
  OR leaving the leader set

---

### Requirement: Participation Engine Reports 9 Metrics + Descriptor

The `participation` engine SHALL compute and return the following raw metrics
from the latest `stock_metrics` snapshot, scoped to the `QUALITY_FILTERS`
universe:

| Metric | Type | Definition |
|---|---|---|
| `breadth_above_ema21` | float [0,1] | % of universe with `distance_to_ema21 >= 0` |
| `breadth_above_ema50` | float [0,1] | % of universe with `distance_to_ema50 >= 0` |
| `breadth_above_ema200` | float [0,1] | % of universe with `current_price > ema200` |
| `breadth_momentum_5d` | float | `breadth_above_ema21` today minus same metric 5 trading days ago |
| `breadth_momentum_20d` | float | same, 20-day window |
| `near_highs_count` | int | count with `distance_to_high_52w_atr >= -1.0` |
| `near_lows_count` | int | count with `distance_to_high_52w_atr <= -6.0` (proxy for "near 52w low") |
| `highs_lows_ratio` | float | `near_highs / max(near_lows, 1)` |
| `participation_persistence` | float | stddev of `breadth_above_ema21` across last 20 calendar days |

The engine SHALL also produce a `descriptor` string drawn from
`EXPANDING / STABLE / NARROWING / COLLAPSING` based on `breadth_momentum_5d`
thresholds:

| descriptor | condition (`breadth_momentum_5d` in percentage points) |
|---|---|
| `EXPANDING` | `> +5.0` |
| `STABLE` | `-5.0 ≤ x ≤ +5.0` |
| `NARROWING` | `-15.0 ≤ x < -5.0` |
| `COLLAPSING` | `< -15.0` |

#### Scenario: All 9 metrics present in participation response

- **WHEN** the endpoint is called
- **THEN** `response.participation.metrics` SHALL contain all 9 keys listed
  above with the documented types

#### Scenario: Descriptor matches momentum threshold

- **GIVEN** `breadth_momentum_5d` of `-0.062` (i.e., -6.2 percentage points)
- **WHEN** the descriptor is computed
- **THEN** it SHALL equal `"NARROWING"`

---

### Requirement: Leadership Quality Engine Reports 10 Metrics + Descriptor

The `leadership_quality` engine SHALL compute and return the following raw
metrics, scoped to the leader set defined by `is_quality_leader`:

| Metric | Type | Definition |
|---|---|---|
| `leader_count` | int | # of Minervini-passing leaders at `as_of` |
| `leader_count_delta_5d` | int | `leader_count` today minus 5 trading days ago |
| `leader_count_delta_20d` | int | same, 20-day window |
| `leader_pullback_quality_avg` | float | avg `pullback_quality_score` across today's leaders |
| `leader_tightness_avg` | float | avg `weekly_tightness` across today's leaders |
| `leader_vol_contraction_avg` | float | avg `weekly_volatility_contraction` across today's leaders |
| `leader_rs_persistence_10d` | float [0,1] | % of today's RS-strong leaders (RS_SPY ≥ 105) that were also RS-strong 10 trading days ago |
| `leader_extension_count` | int | # of leaders with `distance_to_ema21_atr > 3.0` |
| `leader_climactic_count` | int | # of leaders with current `adr_percent > 2 ×` their 20-day avg `adr_percent` |
| `leadership_turnover_5d` | int | size of the symmetric difference between today's leader set and the leader set 5 trading days ago |

The engine SHALL also produce a `descriptor` string drawn from
`EXPANDING / HEALTHY / THINNING / COLLAPSING / EXHAUSTED`. Exhaustion overrides
direction (a leadership set growing in number but with high climactic ratio
SHALL be classified `EXHAUSTED`, not `EXPANDING`):

| descriptor | condition |
|---|---|
| `EXHAUSTED` | `climactic_count / leader_count > 0.25` OR `extension_count / leader_count > 0.40` |
| `EXPANDING` | `delta_5d_pct > +5%` (and not EXHAUSTED) |
| `HEALTHY` | `-5% ≤ delta_5d_pct ≤ +5%` (and not EXHAUSTED) |
| `THINNING` | `-15% ≤ delta_5d_pct < -5%` (and not EXHAUSTED) |
| `COLLAPSING` | `delta_5d_pct < -15%` (and not EXHAUSTED) |

where `delta_5d_pct = (leader_count - leader_count_5d_ago) / leader_count_5d_ago * 100`.

#### Scenario: All 10 metrics present in leadership response

- **WHEN** the endpoint is called
- **THEN** `response.leadership.metrics` SHALL contain all 10 keys listed
  above with the documented types

#### Scenario: Exhaustion overrides expansion

- **GIVEN** `leader_count = 100`, `leader_count_5d_ago = 90` (delta_5d_pct = +11%)
- **AND** `climactic_count = 30` (climactic_ratio = 0.30)
- **WHEN** the descriptor is computed
- **THEN** it SHALL equal `"EXHAUSTED"`, NOT `"EXPANDING"`

#### Scenario: Empty leader set degrades gracefully

- **GIVEN** zero leaders pass `is_quality_leader` at `as_of`
- **WHEN** `leadership_quality` is computed
- **THEN** `leader_count` SHALL be `0`
- **AND** averages (`leader_pullback_quality_avg`, etc.) SHALL be `0.0`
- **AND** the descriptor SHALL be `"COLLAPSING"`
- **AND** the endpoint SHALL NOT raise

---

### Requirement: System SHALL Honestly Report Historical Sample Size

The response SHALL expose `delta_sample_size_20d` so that operators see honestly how many symbols backed the 20-day delta calculation, because `stock_metrics` history has bounded depth (currently ~22 days) and the 20-day window may operate over a reduced subset of the universe.

The system SHALL NOT silently substitute "today's universe" for "20-day-ago
universe" when historical rows are missing.

#### Scenario: Sample size exposed in response

- **WHEN** the endpoint is called
- **THEN** `response.participation.delta_sample_size_20d` SHALL be present
  and equal to the count of `stock_metrics` rows at `as_of - 28 calendar days`
  matching `QUALITY_FILTERS`

#### Scenario: Insufficient history degrades, never fabricates

- **GIVEN** zero `stock_metrics` rows exist 20 trading days ago
- **WHEN** the endpoint is called
- **THEN** `breadth_momentum_20d` SHALL be `0.0`
- **AND** `delta_sample_size_20d` SHALL be `0`
- **AND** the endpoint SHALL NOT raise or default to today's breadth

---

### Requirement: API Contract for `/market-context/current`

The endpoint `GET /api/v1/market-context/current` SHALL return a JSON object
with the following top-level structure:

```jsonc
{
  "as_of": "YYYY-MM-DD",            // date of latest stock_metrics
  "universe_size": <int>,            // # rows passing QUALITY_FILTERS at as_of
  "participation": {
    "descriptor": "<string>",        // EXPANDING/STABLE/NARROWING/COLLAPSING
    "delta_5d": <float>,             // breadth_momentum_5d × 100
    "delta_sample_size_20d": <int>,
    "metrics": { /* 9 raw metrics */ }
  },
  "leadership": {
    "descriptor": "<string>",        // EXPANDING/HEALTHY/THINNING/COLLAPSING/EXHAUSTED
    "delta_5d": <float>,             // leader_count_delta_5d as % change
    "metrics": { /* 10 raw metrics */ }
  },
  "engines_pending": [
    "persistence", "forgiveness", "rotation", "volatility", "follow_through"
  ]
}
```

#### Scenario: Empty database returns 404

- **GIVEN** zero rows in `stock_metrics`
- **WHEN** the endpoint is called
- **THEN** the response status SHALL be `404`
- **AND** the body SHALL contain a clear error message about no data available

#### Scenario: Engines pending list is exactly five entries

- **WHEN** the endpoint is called against a valid database
- **THEN** `engines_pending` SHALL be exactly:
  `["persistence", "forgiveness", "rotation", "volatility", "follow_through"]`
- **AND** the list order SHALL be deterministic across calls

---

### Requirement: Response Cached In-Memory, TTL 5 Minutes

The full `MarketContext` response SHALL be cached in-memory keyed by `as_of`
date with a TTL of approximately 5 minutes. The engine performs ~17 queries
per cold call; with frontend polling every 60 seconds, the cache is
load-bearing in the absence of Redis.

The cache SHALL invalidate automatically when the underlying `as_of` date
changes (i.e., a new trading day's metrics arrive).

#### Scenario: Repeated calls within TTL hit cache

- **GIVEN** an initial call at time T returns context for `as_of = D`
- **WHEN** a second call is made at time `T + 60s`
- **THEN** the response SHALL be served from the in-memory cache (no DB queries)

#### Scenario: New trading day invalidates cache

- **GIVEN** cached context for `as_of = 2026-05-23`
- **WHEN** `stock_metrics` receives new rows for `2026-05-24` and the endpoint
  is called
- **THEN** the cache SHALL be bypassed and a fresh computation performed
- **AND** the new response SHALL have `as_of = 2026-05-24`

---

### Requirement: Coexistence With Legacy `MarketRegimeEngine`

This phase SHALL NOT delete, modify, or alter the behavior of the existing
`MarketRegimeEngine` service (`backend/app/services/market_regime_engine.py`)
nor its endpoint `GET /api/v1/market-regime/current`. Both systems run in
parallel.

The new `market-context` capability is additive. Deletion of the legacy regime
engine is the subject of a separate future change after the new engine is
validated against operator use.

#### Scenario: Legacy endpoint remains functional

- **WHEN** `GET /api/v1/market-regime/current` is called after this change
  is deployed
- **THEN** it SHALL continue to return the same shape it did before,
  preserving backwards compatibility for any unmigrated consumer
