## Why

Calibration currently counts an `entering_pullback` as successful when it advances 1.5 ATR while avoiding an EMA50 closing break. That can reward a failed EMA9/EMA21 pullback which reaches EMA50 before rebounding. The operator's setup instead requires a recovered EMA9/EMA21 test followed by continuation within ten subsequent sessions. This change protects transition-first interpretation, deterioration-first evaluation, and inspectable evidence.

## What Changes

- Give `entering_pullback` its own chronological outcome rule: recovered EMA9/EMA21 test, then continuation of at least the existing 1.5 ATR from the detection price on a later session within the ten-session window.
- Allow intraday wicks below EMA9/EMA21 if support recovers at the close. A close below EMA21 or an intraday touch of EMA50 invalidates the outcome before success is considered.
- Require completed price sessions, excluding the mutable as-of day's bar for this transition.
- Reclassify pullbacks from ordered stored prices rather than max/min summaries, and reset legacy resolved pullback labels to pending through an Alembic data migration so they cannot silently retain the old definition.
- Explain the pullback outcome rule on Calibration.

## Capabilities

### New Capabilities

- `entering-pullback-outcomes`: Deterministic chronological support-and-continuation outcomes and safe historical re-evaluation for entering pullbacks.

### Modified Capabilities

None. Calibration cohorts and rate formulas remain unchanged.

## Impact

- `backend/app/services/outcome_tracker.py`, a focused pure outcome helper, Calibration's reclassification endpoint, a data-only Alembic migration, and backend regression tests.
- `frontend/app/calibration/page.tsx` receives a short explanation of the new rule.
- No new dependencies or schema fields. No production migration, backfill, deployment, or reclassification is performed as part of implementation.
- The archived outcome-tracking spec groups entering pullbacks with pre-reclaim signals and describes an older EMA21-reach rule. This new capability supersedes that family's outcome semantics only for `entering_pullback`; the other transitions retain their current executable behavior.

## Non-goals

- Change transition detection, eligibility, quality filters, regime selection, cohort sample thresholds, or other transition outcome rules.
- Claim predictive trading probabilities or introduce a trading execution model.
- Build a general market-calendar/backtesting engine or reconstruct intraday ordering from daily OHLC.
