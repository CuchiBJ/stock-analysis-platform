## ADDED Requirements

### Requirement: Diagnostics SHALL reflect queue-specific 52-week-high eligibility

The symbol diagnostic SHALL omit the `distance_to_high_52w_atr >= -3.0` pass/fail criterion from Top Actionable because that value is graded in pullback quality. The Live Transition Feed diagnostic SHALL retain that criterion. Human-readable criteria SHALL not describe a graded actionable signal as a hard exclusion.

The diagnostic's actionable score breakdown SHALL use the same five-session RS baseline and component calculation as the Top Actionable endpoint.

**Implementation:** `backend/app/services/symbol_diagnostic.py`, `backend/app/api/v1/endpoints/stocks.py`, `backend/app/services/actionable_ranking.py`

#### Scenario: Far-from-high symbol gets different actionable and live diagnoses

- **Given** a symbol satisfies every shared structural condition and trigger
- **And** its `distance_to_high_52w_atr=-4.39`
- **When** the diagnostics are generated
- **Then** the Top Actionable diagnostic SHALL not fail on 52-week-high distance
- **And** the Live Transition Feed diagnostic SHALL fail the `>= -3.0` criterion
