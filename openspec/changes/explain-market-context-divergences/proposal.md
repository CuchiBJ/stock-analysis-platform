## Why
A rising index can mask falling participation or fewer leaders. Operators currently have to compare separate rows mentally; explicit, evidenced opposing movements reduce scanning effort and make deterioration visible without predicting a reversal.

## What Changes
- Add a compact dedicated-page section for opposing session movements between each of SPY/QQQ and participation/leader count.
- Reuse the validated dates, rounded direction and evidence from the session-change summary.
- Distinguish no opposing movements from incomplete or unavailable comparisons, with explicit coverage.

## Capabilities
### New Capabilities
- `market-context-divergences`: deterministic session divergence explanations and coverage.
### Modified Capabilities
None.

## Non-goals
No multi-session technical divergence detection, forecasts, recommendations, posture/policy/scoring changes, VIX divergence rules, sector evolution, dashboard changes or deployment.

## Impact
Frontend-only helper, component, page integration and tests. No API/schema/dependency changes. Existing changes remain intact.
