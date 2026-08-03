## Why

Calibration currently answers whether a transition worked across the complete observed history, but it does not answer whether the same setup is being paid in the present market context. Treating an unconditional historical rate as current evidence violates the product principle that regime affects everything and can create false confidence precisely when recent follow-through is deteriorating.

## What Changes

- Extend calibration reporting with an all-history cohort, a 21-day rolling recent cohort aligned with follow-through, and a cohort matched to the current market regime.
- Report delivery-rate deltas, sample sufficiency, confidence intervals, and an interpretable drift state per bullish transition type.
- Add a compressed current-context summary so Calibration states whether the market is paying recent signals and which evidence is comparable to today.
- Make empirical continuation lookup context-aware, with a deterministic fallback ladder and conservative minimum samples.
- Wire each actionable setup's actual operational transition into empirical probability lookup, rather than silently falling back to the rule-based formula.
- Anchor regime detection to the same `as_of` snapshot used by MarketContext and reuse that regime across Calibration and actionable scoring.
- Compare recent calibration against the non-overlapping 180-day baseline used by follow-through, and always explain `NOT_PAYING` in posture reasons.
- Reclassify existing observation regime labels from their detection-date snapshots so historical regime cohorts are not polluted by the former all-history calculation.
- Preserve the rule-based fallback whenever no trustworthy comparable cohort exists.

## Capabilities

### New Capabilities

- `context-aware-empirical-probability`: Context-conditioned empirical continuation probabilities and fallback behavior for actionable setups.
- `market-context-consistency`: Shared as-of regime context, non-overlapping follow-through baselines, and complete posture explanations.

### Modified Capabilities

- `calibration-reporting`: Add recent and current-regime cohorts, uncertainty, drift classification, and current follow-through context to the calibration API and page.
- `market-regime`: Require every regime factor to use one resolved `stock_metrics` snapshot rather than aggregating historical rows.

## Impact

- Backend calibration API, empirical probability calculator, actionable transitions endpoint, and related tests.
- Frontend Calibration page response model and presentation.
- No schema migration is required: `regime_at_detection`, transition type, RS, outcome status, and detection date are already persisted. Existing regime labels require a deterministic data reclassification.
- `market_context_engine.py` is already larger than 400 lines; this change reuses its public analysis result and keeps new cohort/reporting logic outside that service rather than expanding it.

## Non-goals

- No guarantee or prediction that an individual trade will succeed.
- No opaque machine-learning model or automated parameter optimization.
- No full walk-forward backtesting engine in this change.
- No new participation/leadership-at-detection segmentation until those fields are persisted without lookahead.
- No change to the definitions of SUCCESS, FAILURE, or NEUTRAL.
