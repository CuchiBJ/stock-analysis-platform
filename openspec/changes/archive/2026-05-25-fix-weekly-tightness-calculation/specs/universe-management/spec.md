## MODIFIED Requirements

### Requirement: weekly_tightness SHALL Be ATR-Normalized and Volume-Gated

The `weekly_tightness` metric stored in `stock_metrics` SHALL measure weekly price range
relative to the stock's daily ATR, not relative to its close price. Weeks with zero volume
SHALL be excluded from the calculation. The metric SHALL return `0.0` for stocks with
insufficient active trading history.

**Correct formula semantics:**

| Condition | Expected `weekly_tightness` |
|---|---|
| Weekly range < 0.5 ATR (very tight base) | ≥ 0.67 |
| Weekly range ≈ 1.0 ATR (normal pullback) | ≈ 0.50 |
| Weekly range > 2.0 ATR (loose structure) | ≤ 0.33 |
| Stock with 0 volume in recent 4 weeks | 0.0 |
| Stock with daily ATR = 0 | 0.0 |

**Implementation:** `backend/app/data/ingestors/metrics_calculator.py`, method `_calculate_weekly_tightness()`

#### Scenario: Inactive stock receives zero tightness

- **WHEN** a stock has `volume == 0` for 3 or more of the last 4 weekly candles
- **THEN** `weekly_tightness` SHALL be `0.0`
- **AND** the stock SHALL NOT pass any filter using `weekly_tightness > threshold`

#### Scenario: Institutional stock in tight base receives high tightness

- **WHEN** a stock has active weekly volume AND its average weekly range over the last 4 weeks is less than 1.0x its 14-day ATR
- **THEN** `weekly_tightness` SHALL be greater than `0.50`

#### Scenario: Loose structure receives low tightness

- **WHEN** a stock's average weekly range exceeds 2.0x its 14-day ATR
- **THEN** `weekly_tightness` SHALL be less than or equal to `0.33`

### Requirement: Quality Swing Scanner SHALL Use weekly_tightness > 0.3

The `quality_swing_scanner_service.py` filter on `weekly_tightness` SHALL be `> 0.3`,
which after ATR-normalization corresponds to stocks with weekly ranges below 2.33x ATR —
the correct institutional threshold for base quality. The emergency value `> 0.02`
is a temporary patch and SHALL be reverted once the formula is fixed and metrics are
recalculated.

**Implementation:** `backend/app/services/quality_swing_scanner_service.py`

#### Scenario: Scanner filters stocks with loose weekly structure

- **WHEN** the scanner runs with default filters
- **THEN** stocks with `weekly_tightness <= 0.3` (weekly range > 2.33 ATR) SHALL NOT appear in results

#### Scenario: Scanner returns institutional setups after recalculation

- **WHEN** `weekly_tightness` is recalculated with the corrected formula AND the scanner runs with default filters
- **THEN** at least one stock from the liquid universe (avg_volume_10d >= 700k, price >= 5.0) SHALL appear in results
