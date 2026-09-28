## Why

Top Actionable Setups currently rejects an otherwise valid institutional pullback when `distance_to_high_52w_atr < -3.0`, even though the same distance is already graded from 20 to 0 points inside `pullback_quality_score`. That duplicate hard gate creates a discontinuity: a candidate at -3.01 ATR disappears rather than ranking slightly below one at -3.00 ATR. The ranking also uses `pullback_quality_score` twice, for both its 40% pullback component and the 15% `leader_quality` component, so the displayed composition overstates one input instead of measuring independent leadership.

This change defends scarcity and setup quality while improving interpretability (Principles 2 and 7): structural, liquidity, trigger, regime, and deterioration protections stay intact; 52-week-high proximity remains visible and graded; and the duplicated component becomes a deterministic relative-strength-during-pullback signal.

## What Changes

- Remove the `distance_to_high_52w_atr >= -3.0` hard eligibility condition only from `GET /api/v1/transitions/actionable`.
- Preserve 52-week-high distance as the existing 0–20 point subcomponent of `pullback_quality_score`.
- Preserve the stricter near-high behavior for the Live Transition Feed and breakout trigger.
- Replace the duplicated 15% `leader_quality` component with `relative_strength_pullback`, calculated from current `relative_strength_spy` and its five-session historical value.
- Use a neutral 50/100 RS component when either current or historical RS is missing; missing history does not exclude or promote a candidate.
- Update symbol diagnostics and frontend score labels to describe the actual behavior.
- Add targeted tests for eligibility boundaries, live/breakout preservation, and improving, stable, deteriorating, and missing RS history.

## Capabilities

### Modified Capabilities

- `priority-engine`: Top Actionable eligibility and its 15% independent leadership component.
- `symbol-diagnostic`: actionable and live pass/fail criteria remain synchronized with their production filters.

## Impact

- Backend: `backend/app/api/v1/endpoints/transitions.py`, `backend/app/api/v1/endpoints/stocks.py`, `backend/app/services/actionable_ranking.py`, `backend/app/services/symbol_diagnostic.py`.
- Frontend: score-component label in `frontend/app/stock/[symbol]/page.tsx`.
- Tests: focused actionable ranking and symbol diagnostic contracts.
- Database/API dependencies: none; uses existing daily `stock_metrics.relative_strength_spy` history.
- Fundamental acceleration is not added because the repository has no trustworthy earnings, revenue, sales, or EPS acceleration field and no ingestion path for one.

## Non-goals

- Do not loosen Live Transition Feed or breakout near-high rules.
- Do not weaken market-cap, volume, ADR, price, one-year performance, EMA50, SMA150, SMA150>SMA200, 52-week-low, EMA9/EMA21 trigger, regime, or deterioration behavior.
- Do not guarantee any specific ticker, including BE, appears above the top-N cutoff.
- Do not add a fundamental data provider, schema field, migration, or speculative proxy.
- Do not recalibrate pullback-quality buckets or other queues.

The endpoint module is already larger than 400 LOC. This work therefore keeps HTTP/filter orchestration in the endpoint but extracts historical RS loading and score calculation into `backend/app/services/actionable_ranking.py`; broader endpoint decomposition is outside this focused change.
