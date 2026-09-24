## ADDED Requirements

### Requirement: Top Actionable SHALL grade 52-week-high distance instead of hard-excluding it

The Top Actionable endpoint SHALL NOT use `distance_to_high_52w_atr` as a pass/fail eligibility condition. It SHALL continue to include the existing distance buckets in `pullback_quality_score`, where the distance contributes 20 points at `>= -1.0` ATR, 15 at `>= -2.0`, 10 at `>= -3.0`, 5 at `>= -4.0`, and 0 below `-4.0` or when missing.

All other actionable protections SHALL remain in force: market capitalization at least $600M; `avg_volume_10d >= 800000`; `adr_percent >= 4.0`; `current_price >= 5.0`; `perf_1y > 30`; price above EMA50 and SMA150; SMA150 above SMA200; price at least `1.5 * low_52w`; `pullback_quality_score >= 55`; and EMA9 or EMA21 ATR distance in `[-1.0, 0.5]`.

**Implementation:** `backend/app/api/v1/endpoints/transitions.py`

#### Scenario: Candidate just beyond the old boundary remains eligible

- **Given** a candidate satisfies every actionable structural, liquidity, quality, and EMA trigger condition
- **And** its `distance_to_high_52w_atr` is `-4.39`
- **When** Top Actionable eligibility is evaluated
- **Then** the distance SHALL NOT exclude the candidate
- **And** its pullback-quality contribution for 52-week-high distance SHALL be 0 points
- **And** appearance SHALL still depend on its final rank and top-N cutoff

#### Scenario: Structural trend remains mandatory

- **Given** a candidate has `distance_to_high_52w_atr=-4.39`
- **And** its SMA150 is not above SMA200
- **When** Top Actionable eligibility is evaluated
- **Then** the candidate SHALL be excluded

### Requirement: Live and breakout near-high behavior SHALL remain strict

The Live Transition Feed SHALL continue to require `distance_to_high_52w_atr >= -3.0`. Breakout surfacing SHALL continue to require `distance_to_high_52w_atr >= -1.0` and EMA21 ATR distance in `(0, 1.5]`.

**Implementation:** `backend/app/api/v1/endpoints/transitions.py`

#### Scenario: Far-from-high candidate is actionable-eligible but not live-eligible

- **Given** a candidate otherwise satisfies both structural filters
- **And** its `distance_to_high_52w_atr=-4.39`
- **When** actionable and live eligibility are evaluated
- **Then** the distance SHALL NOT fail actionable eligibility
- **And** it SHALL fail live eligibility

#### Scenario: Breakout boundary remains unchanged

- **Given** EMA21 ATR distance is `1.0`
- **When** 52-week-high ATR distance is `-1.0`
- **Then** the breakout position trigger SHALL pass
- **But When** 52-week-high ATR distance is `-1.01`
- **Then** the trigger SHALL fail

### Requirement: Actionable ranking SHALL use independent RS leadership during pullback

The 15% actionable ranking component formerly named `leader_quality` SHALL be replaced by `relative_strength_pullback`. It SHALL combine 60% current RS-vs-SPY level and 40% five-session RS-vs-SPY percentage direction using the explicit buckets in the change design. It SHALL NOT reuse `pullback_quality_score`.

Missing current or baseline RS SHALL produce a neutral component score of 50 and SHALL NOT exclude the candidate. The score breakdown SHALL expose the inputs, sub-scores, delta, and status.

**Implementation:** `backend/app/api/v1/endpoints/transitions.py`, `backend/app/services/actionable_ranking.py`

#### Scenario: Improving leadership is rewarded

- **Given** current RS-vs-SPY is 108 and the five-session baseline is 104
- **When** the component is calculated
- **Then** the level score SHALL be 80
- **And** the trend score SHALL be 100
- **And** the component SHALL equal 88

#### Scenario: Stable leadership remains positive but below improvement

- **Given** current and baseline RS-vs-SPY are both 106
- **When** the component is calculated
- **Then** the status SHALL be `stable`
- **And** the component SHALL equal 72

#### Scenario: Deteriorating leadership is penalized

- **Given** current RS-vs-SPY is 98 and the baseline is 106
- **When** the component is calculated
- **Then** the status SHALL be `deteriorating`
- **And** the component SHALL equal 24

#### Scenario: Missing history is neutral

- **Given** current RS-vs-SPY is 108 and no baseline exists
- **When** the component is calculated
- **Then** the component SHALL equal 50
- **And** its status SHALL be `missing_history_neutral`
