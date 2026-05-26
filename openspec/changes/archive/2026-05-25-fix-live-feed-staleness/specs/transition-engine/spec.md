## ADDED Requirements

### Requirement: Live Feed SHALL Only Show Current-Day Setups

The `/transitions/live` endpoint SHALL only surface stocks whose most recent metrics row in the database corresponds to `MAX(date)` across all stock_metrics. A stock whose latest data is from a previous day SHALL NOT appear in the feed, regardless of whether that older data would have passed the trigger filter.

**Implementation:** `backend/app/api/v1/endpoints/transitions.py`, `get_live_transitions()`

#### Scenario: Setup that bounced yesterday does not appear today

- **WHEN** a stock (e.g. NBIS) was in the EMA trigger zone on day D-1 but on day D its metrics show it outside the trigger zone (e.g. bounced strongly)
- **THEN** the feed on day D SHALL NOT include that stock
- **AND** the feed SHALL use day D's metrics as the "current" state, not day D-1's

#### Scenario: Setup active today appears correctly

- **WHEN** a stock's latest metrics (from `MAX(date)`) pass both the institutional quality gates and the EMA proximity trigger
- **THEN** the feed SHALL include that stock with the transition calculated against the previous trading day's metrics

#### Scenario: Feed is empty when no stocks qualify today

- **WHEN** no stock has metrics from `MAX(date)` that pass both quality gates and EMA trigger
- **THEN** the feed SHALL return an empty list
- **AND** this is a valid operational state (scarcity is signal)

#### Scenario: Weekend/holiday gap does not break direction calculation

- **WHEN** `MAX(date)` is a Monday and the previous trading day is a Friday (3 calendar days ago)
- **THEN** the endpoint SHALL still find the Friday metrics as "previous" for direction calculation
- **AND** `ema9_distance_change` and `ema21_distance_change` SHALL be calculated correctly
