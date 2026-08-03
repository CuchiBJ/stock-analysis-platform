## Why

Market Health currently requires five strictly consecutive clean sessions to leave `DAMAGED`/`FRAGILE`. Because ordinary recovery pullbacks often produce `NARROWING` participation or `THINNING` leadership, mild deterioration resets all repair progress and can keep the operational posture `DEFENSIVO` indefinitely even while the market is making a credible, uneven recovery. This change protects interpretability and operational clarity by distinguishing a normal pullback from a severe relapse.

## What Changes

- Classify each market-health day as `clean`, `mild`, or `severe` instead of treating every adverse descriptor identically.
- Define mild deterioration as participation `NARROWING` or leadership `THINNING`; define severe deterioration as participation/leadership `COLLAPSING` or leadership `EXHAUSTED`.
- Replace the five-consecutive-session recovery gate with a tolerant rule: at least five clean sessions in the latest seven and no severe deterioration in the latest three.
- Preserve the existing 20-session damage memory, damaged-day count, episode count, and posture ceilings.
- Expose repair-window progress and daily severity through the Market Context API and drawer so the operator can understand why recovery is or is not unlocked.
- Extract the pure recovery/severity policy from the >400 LOC `market_context_engine.py` service into a focused module while retaining database aggregation in the engine.

## Non-goals

- Do not change participation or leadership descriptor thresholds.
- Do not change the quality universe, leader gate, follow-through classifier, or `NOT_PAYING` posture ceiling.
- Do not make Market Health predictive or introduce ML.
- Do not remove `damaged_days`, `episodes`, `repair_streak`, or other existing API fields.
- Do not persist intraday health classifications.

## Capabilities

### New Capabilities

- `market-health-recovery`: Severity-aware market damage memory, tolerant recovery qualification, and interpretable recovery progress.

### Modified Capabilities

- `market-context-presentation`: Display mild versus severe damage and the rolling recovery qualification in the Market Context drawer and tooltip.

## Impact

- Backend: `market_context_engine.py`, `market_posture.py`, a new pure market-health policy module, and Market Context endpoint serialization.
- Frontend: `MarketContextBar.tsx` and `MarketContextDrawer.tsx` health types, damage strip, tooltip, and recovery metrics.
- Tests: market-health state/classification and posture explanation regression coverage.
- APIs: additive health fields and additive per-day `severity`; existing fields remain compatible.
- Dependencies and database: no new dependencies or migrations.
