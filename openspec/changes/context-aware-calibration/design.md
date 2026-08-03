## Context

`GET /calibration/by-transition-type` currently aggregates every observation by transition type. The database already records `date_detected`, `regime_at_detection`, RS at detection, and raw outcomes, while `MarketContextEngine` separately computes a recent follow-through window. The actionable endpoint calculates a continuation probability but omits the transition type, so its empirical lookup always falls back to the rule-based formula.

The change spans reporting, probability selection, endpoint wiring, and UI. It must remain interpretable and avoid lookahead: cohort membership uses only attributes stored at detection time.

## Goals / Non-Goals

**Goals:**

- Make the difference between historical evidence and evidence comparable to today explicit.
- Detect recent deterioration or improvement without claiming certainty.
- Use current regime and RS-at-detection when selecting empirical probabilities.
- Preserve a conservative, visible rule-based fallback.
- Keep the Calibration page operationally compressed.

**Non-Goals:**

- Predict individual trade outcomes or optimize thresholds automatically.
- Add an opaque ML model.
- Reconstruct participation or leadership at detection from present-day data.
- Change outcome labels or build full walk-forward backtesting.

## Decisions

### Return three explicit cohorts per transition

Each row will expose `historical`, `recent`, and `current_regime` cohort objects. Recent means signals detected in the last 21 calendar days relative to the latest metrics date, aligned with the follow-through engine's active window. Current-regime means all observations whose persisted `regime_at_detection` matches today's regime.

This keeps the existing all-history view while making the relevant comparison visible. A single blended score was rejected because it hides whether evidence is recent, comparable, or merely abundant.

### Use delivery rate as the operational comparison

Drift compares `SUCCESS / (SUCCESS + FAILURE + NEUTRAL)`, because a neutral signal consumed attention without delivering the required move. Win rate remains available for diagnostic continuity but does not drive drift.

### Quantify uncertainty with Wilson intervals

Every empirical delivery rate will include a 95% Wilson confidence interval. A cohort requires 20 settled observations before its rate or interval is surfaced. Drift is `deteriorating` or `improving` only when both historical and recent cohorts are empirical and their Wilson intervals do not overlap; otherwise it is `stable` or `insufficient`.

A raw percentage-point threshold was rejected because it overreacts to small cohorts.

### Reuse current market context instead of duplicating follow-through logic

`MarketRegimeEngine.detect_regime(target)` will first resolve one metrics date at or before `target`, then apply that exact date to all five factor queries. `MarketContextEngine` will own the resulting regime analysis for its `as_of`; Calibration and actionable scoring will consume that same value instead of invoking an independent current-regime calculation. Cohort aggregation remains in calibration reporting, outside the already-large market context service.

Existing observation labels were produced by the former all-history regime calculation. A deterministic admin reclassification will group observations by `date_detected`, reconstruct the regime as of each date, update `regime_at_detection`, and clear empirical caches.

### Compare recent performance to a non-overlapping baseline

Calibration will retain all-history evidence but add a `baseline` cohort covering the 180 calendar days immediately before the 21-day recent window. Drift and `recent_delta_pp` will compare recent against this baseline, matching `MarketContextEngine._follow_through()` boundaries. Comparing against all history was rejected because the recent sample is contained inside it and statistically attenuates drift.

### Explain suppressive evidence even when another constraint is stronger

`NOT_PAYING` will always appear in posture reasons. It remains a ceiling at `SELECTIVO` and will never raise an already defensive posture; the change is explanatory, not a new scoring rule.

### Use a conservative empirical fallback ladder

Empirical continuation lookup will receive the actual transition, RS, current regime, and setup date. Its probability is the delivered rate `SUCCESS / (SUCCESS + FAILURE + NEUTRAL)`, not the inflated decisive-only win rate. The ladder is:

1. transition + current 21-day window + regime + RS bucket, minimum 20 settled outcomes;
2. transition + current 21-day window, minimum 30;
3. transition + regime + RS bucket, minimum 20;
4. transition + regime, minimum 30;
5. transition + RS bucket, minimum 30;
6. transition across all contexts, minimum 50;
7. rule-based fallback.

This prefers relevance over sample size without treating tiny cohorts as evidence. The result exposes its cohort/basis so the caller can explain it.

### Calculate actionable transitions in bulk

The actionable endpoint will fetch the prior metrics row for its candidate symbols in one query, calculate each actual operational transition, and pass its value to continuation probability lookup. Stable or unavailable transitions intentionally use the rule-based fallback.

## Risks / Trade-offs

- [Reclassification can change large numbers of observation labels] → Derive labels only from persisted historical metrics at or before each detection date and expose evaluated/changed counts.
- [Wilson non-overlap is conservative and may often say stable] → Prefer missed weak signals over false drift alarms.
- [Regime labels may evolve over time] → Cohorts use the label persisted at detection; changes to regime definitions require explicit reclassification, not silent reconstruction.
- [Correlated daily observations are not independent trials] → Confidence intervals are presented as uncertainty guidance, not formal causal proof; full de-duplication is deferred.
- [Additional endpoint queries increase latency] → Aggregate cohorts in grouped SQL queries and reuse cached market context.

## Migration Plan

1. Deploy additive backend response fields while retaining the legacy top-level row fields.
2. Deploy the frontend against the expanded response.
3. Enable context-aware empirical lookup and actionable transition wiring.
4. Run regime-label reclassification and inspect evaluated/changed counts.
5. Rollback code independently; observation labels can be reclassified again from any prior regime implementation if needed.

## Open Questions

- Persisting participation, leadership, posture, and predicted probability at detection remains the next step for true out-of-sample calibration.
