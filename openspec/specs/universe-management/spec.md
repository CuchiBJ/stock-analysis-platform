# universe-management

## Purpose

Define how the tradeable universe is constructed, filtered for quality, and kept
fresh. The universe is the input to every other capability — its integrity
determines whether downstream signals are institutional or contaminated by
penny-stock noise.

## Scope

**In scope:**
- Universe seed source (SEC EDGAR + NASDAQ/NYSE listings)
- Quality filters applied to all breadth, leadership, and regime calculations
- Universe refresh cadence and lifecycle (active / inactive / delisted)
- Daily price ingestion (yfinance fallback, Polygon.io primary)
- Daily metrics calculation that feeds all other capabilities

**Out of scope:**
- Setup detection (see [setup-lifecycle](../setup-lifecycle/spec.md))
- Scoring or ranking (see [priority-engine](../priority-engine/spec.md))
- Intraday tick data (handled by realtime_price_service)

## Requirements

### Requirement: Universe Source SHALL be SEC EDGAR + Major Exchanges

The system SHALL build its universe from authoritative listings of US-traded
common stock. The current implementation seeds from SEC EDGAR (`company_tickers.json`)
filtered to NASDAQ and NYSE.

**Implementation:** `backend/app/universe/sources/` and
`scripts/load_full_universe.py`

#### Scenario: Universe load creates expected ticker count

- **Given** a fresh database
- **When** `scripts/load_full_universe.py` runs to completion
- **Then** the `stocks` table contains ≥ 2500 active tickers from NASDAQ/NYSE
- **And** every row has `exchange ∈ {NASDAQ, NYSE}` and `is_active = true`

#### Scenario: ETFs, ADRs, and OTC are excluded

- **Given** a universe load run
- **When** the source returns mixed instruments
- **Then** ETFs, ADRs, preferred shares, units, warrants, and OTC tickers SHALL NOT
  be persisted as stocks

---

### Requirement: Quality Filters SHALL Apply Uniformly to All Universe Calculations

Every breadth, leadership, regime, and ranking calculation SHALL filter the
universe by the canonical `QUALITY_FILTERS` constraints. Bypassing this filter
in any new query is a violation.

**Canonical thresholds** (`backend/app/services/universe_filters.py`):
- `avg_volume_10d >= 500_000`
- `current_price >= 5.0`
- `adr_percent >= 2.0`
- `adr_percent IS NOT NULL`

**Implementation:** `backend/app/services/universe_filters.py:1-12`

#### Scenario: Penny stocks excluded from regime breadth

- **Given** the universe contains a stock with `current_price = 2.5`
- **When** `MarketRegimeEngine._calculate_breadth_quality()` runs
- **Then** that stock SHALL NOT appear in either numerator or denominator
- **And** the breadth quality reflects only stocks meeting all four filters

#### Scenario: Illiquid stocks excluded from leadership

- **Given** a stock with `avg_volume_10d = 100_000` and `pullback_quality_score = 80`
- **When** leadership health is calculated
- **Then** the stock SHALL NOT be counted as a leader, regardless of its quality score

#### Scenario: Adding a new query SHALL apply the filter

- **Given** a new service introduces a query against `StockMetrics`
- **When** the query computes any aggregate or ratio interpreted as "the market" or "leaders"
- **Then** the query SHALL include `QUALITY_FILTERS` (e.g. `.where(*QUALITY_FILTERS)`)

---

### Requirement: Universe Refresh SHALL be Idempotent

A re-run of universe loading SHALL NOT duplicate tickers, reset `is_active`
flags incorrectly, or destroy historical price/metric rows.

**Implementation:** `backend/app/universe/lifecycle/` and `scripts/load_full_universe.py`

#### Scenario: Re-running load preserves history

- **Given** the universe was loaded yesterday with 2761 tickers
- **And** today 5 tickers were delisted
- **When** `scripts/load_full_universe.py` runs today
- **Then** the 5 delisted tickers SHALL be marked `is_active = false`
- **And** their historical `stock_prices` rows SHALL remain intact
- **And** the remaining 2756 tickers SHALL retain their existing `id`

#### Scenario: New listings are added on refresh

- **Given** the universe load ran successfully yesterday
- **When** the load runs today and finds 3 new IPOs listed on NASDAQ
- **Then** 3 new rows SHALL be inserted into `stocks` with `is_active = true`
- **And** existing tickers SHALL NOT be re-inserted

---

### Requirement: Daily Price Ingestion SHALL Populate StockMetrics

For every active ticker, a daily metrics row SHALL be computed and persisted
each trading day, containing at minimum:
- `current_price`, `avg_volume_10d`, `relative_volume`
- `adr_percent`, `atr`, `atr_percent`
- `distance_to_ema21`, `distance_to_ema50`, `distance_to_ema21_atr`, `distance_to_ema50_atr`
- `relative_strength_spy`
- `weekly_trend_quality`, `weekly_tightness`, `weekly_volatility_contraction`
- `pullback_quality_score`

**Implementation:** `scripts/recalculate_metrics_with_atr.py`, scheduler job

#### Scenario: Metrics exist for all active tickers after EOD

- **Given** the scheduler ran the post-close metrics job
- **When** queries inspect `stock_metrics` for today's date
- **Then** every `is_active = true` stock SHALL have exactly one row for today
- **And** ATR-normalized distance columns SHALL be populated (not NULL) when
  the stock has ≥ 50 days of price history

#### Scenario: Missing price data does not block metrics for others

- **Given** ticker XYZ has a yfinance fetch failure
- **When** the metrics job processes the batch containing XYZ
- **Then** XYZ SHALL be logged and skipped
- **And** other tickers in the batch SHALL still have metrics persisted

---

### Requirement: Universe Date Column SHALL Use Native DATE Type

The `date` column on `stock_prices` and `stock_metrics` SHALL be PostgreSQL
`DATE`, not `VARCHAR(10)`. This is currently a known violation flagged in the
May 2026 institutional audit and is tracked as a pending change.

**Implementation:** pending migration; see audit findings.

#### Scenario: Date comparisons use index, not string

- **Given** the migration to native DATE is complete
- **When** a query filters by `date >= '2026-05-01'`
- **Then** the query plan SHALL use a B-tree index on the DATE column
- **And** queries SHALL NOT cast strings at filter time
