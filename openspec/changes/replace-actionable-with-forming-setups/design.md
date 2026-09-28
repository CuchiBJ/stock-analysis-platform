## Context

The dashboard currently places Top Actionable Setups above the Setup Feed. Both surfaces draw from closely related institutional/EMA inputs, but only the Setup Feed participates in the operator's execution workflow. Top Actionable ranks static latest metrics with a compound score whose 25% freshness component reads `setup_state_log.entered_at`. That clock measures age in a broad lifecycle state, not age of the current operational opportunity. BE demonstrated the mismatch on 2026-09-24: the production snapshot had price `-0.09 ATR` from EMA9, pullback quality `62`, intact long-term structure, and a new `entering_pullback` observation, while the ranking treated the setup as 21+ days old.

The change crosses backend selection/ranking, diagnostics, chat tools, the dashboard, and operator documentation. `backend/app/api/v1/endpoints/transitions.py` is already well over 400 lines, so adding another ranking path there would worsen an existing ownership problem.

The completed but unarchived `refine-actionable-ranking` change improved the current endpoint's 52-week-high and RS behavior. This change supersedes its user-facing Top Actionable surface but preserves its useful pure RS-history calculation for reuse where appropriate. Archive/apply ordering must avoid restoring retired actionable requirements after this change.

## Goals / Non-Goals

**Goals:**

- Make the dashboard a linear workflow: market context → scarce preparation list → executable Setup Feed.
- Surface up to six institutional-quality structures that are forming toward, but have not yet entered, a current qualifying Setup Feed transition.
- Detect deterioration and structural failure before positive scoring.
- Allow BE/DOCN-shaped pullbacks farther from the 52-week high without a discontinuous near-high gate.
- Rank preparation readiness with explainable, deterministic components and no state-age freshness penalty.
- Keep the diagnostic page capable of explaining eligibility, rank, score leakage, and promotion to the feed.

**Non-Goals:**

- Change operational transition classification or Setup Feed ordering.
- Expand result count beyond six or guarantee named symbols.
- Add user-defined screener controls, predictions, alerts, order execution, data providers, or black-box scoring.
- Redesign queue lenses outside the dashboard.

## Decisions

### D1: Add a formation service and endpoint; do not grow the transitions endpoint

Create `backend/app/services/forming_setup_service.py` to own candidate loading, invalidation, score calculation, live-feed exclusion, narratives, and response assembly. Expose it through `GET /api/v1/transitions/forming?limit=6` initially, then remove the old actionable route and in-repository callers in the same release.

Alternative considered: repurpose `/transitions/actionable` in place. Rejected because the old name and response semantics would keep misleading diagnostics, chat tools, and future maintainers, and would make rollback ambiguous.

### D2: Use a two-stage pipeline: eligibility/invalidation, then ranking

Stage one uses the latest metrics row per symbol, the canonical `QUALITY_FILTERS`, market capitalization of at least $600M, price above EMA50 and SMA150, SMA150 above SMA200, price at least `1.5 × low_52w`, and `perf_1y > 30`. It then runs the existing setup invalidation engine. Any `BROKEN`, `DISTRIBUTION`, or invalidated candidate is rejected before scoring.

There is no hard `distance_to_high_52w_atr` predicate and no requirement that EMA9/EMA21 already be inside the Setup Feed trigger band. The 52-week-high distance is returned as context. This preserves institutional structure while allowing earlier pullbacks and contractions to surface.

Alternative considered: simply widen the old near-high gate from three to five ATR. Rejected because it creates another cliff and still confuses structural quality with preparation timing.

### D3: Exclude current executable signals so the panels complement each other

The service shall consume a reusable live-transition snapshot/selector extracted from the current endpoint logic. A symbol with a current qualifying non-stable transition returned by the Setup Feed is excluded from Setups Forming. Historical observation rows alone are not sufficient because the scanner can record multiple observations during a day and they do not prove that the transition remains current.

Alternative considered: allow duplicates with different badges. Rejected because it raises cognitive load and makes the two panels compete.

### D4: Replace state-age freshness with formation readiness

The initial `formation_score` is a 0–100 weighted score:

- **Trigger readiness and direction — 35%**: ATR-normalized distance to the nearest EMA9/EMA21 trigger boundary plus whether that distance is converging across recent sessions.
- **Structural integrity — 25%**: weekly trend quality, EMA50 buffer/slope evidence available in current metrics, and intact long-term moving-average structure.
- **Orderliness and contraction — 20%**: volume contraction, relative-volume dry-up, weekly tightness, and volatility contraction.
- **Relative-strength trajectory — 10%**: current versus five-session RS direction. It is context, not a hard gate; missing history is neutral.
- **Regime and group alignment — 10%**: deterministic context/group contribution with warnings retained in the response.

State age is returned as `structural_age_days` but contributes zero points. Setups Forming does not claim signal freshness; the Setup Feed owns the age of executable transitions. The implementation must expose every component and input used, and the threshold buckets must be calibrated against the current production distribution before being frozen in code. Calibration may move bucket boundaries but not weights or eligibility without updating the spec.

Alternative considered: reset `days_in_state` whenever an `entering_pullback` observation appears. Rejected because repeated intraday/daily observations could make a long-running episode look perpetually fresh. A future explicit transition-episode model may add opportunity age, but it is not required for this preparation list.

### D5: Preserve scarcity and allow an honest empty state

Return at most six candidates with a default minimum formation score of 55. Never lower the threshold to fill the panel. Sort by formation score descending, then trigger proximity, then structural integrity. The response includes total eligible count and context snapshot so the UI can distinguish scarcity from data failure.

### D6: Put preparation before execution without confusing their roles

Place Setups Forming above the Setup Feed in dashboard reading order, following the operator's explicit preference. The upper panel is preparation only; the Setup Feed remains the execution surface. The formation panel uses compact cards and preparation language: why it is forming, distance to the next trigger, structure/volume evidence, RS direction, and the most important risk. It must not show continuation probability, “actionable”, confidence, buy language, or a stale/fresh badge derived from structural age.

### D7: Keep diagnosis synchronized by sharing pure rules

Eligibility predicates, score calculation, live-feed exclusion, and score breakdown must be pure/shared surfaces called by both the production endpoint and symbol diagnostics. The diagnostic list key becomes `forming`; it reports one of `eligible_ranked`, `eligible_below_cutoff`, `promoted_to_feed`, or `ineligible`, with explicit criteria and score components.

### D8: Reconcile the preceding actionable-ranking change explicitly

Implementation starts by ensuring `refine-actionable-ranking` is archived or otherwise incorporated. Its five-session RS helper may remain; actionable endpoint-specific score wiring, tests, diagnostic copy, and guide text are removed or migrated. This prevents two active specifications from claiming the same dashboard surface.

## Risks / Trade-offs

- **[Risk] The new panel becomes a generic screener.** → Keep a hard maximum of six, retain institutional/invalidation gates, provide compact narratives, and allow an empty result.
- **[Risk] Removing the near-high gate admits damaged laggards.** → Preserve long-term structure, run invalidation first, expose RS deterioration, and require minimum formation score.
- **[Risk] Excluding live symbols drifts from the actual feed.** → Share the live selector/service rather than reimplementing transition rules or inferring from stale observation rows.
- **[Risk] Weight changes merely encode the BE outcome.** → Validate against a broader historical fixture set including successful and failed formations; BE and DOCN are shape examples, not golden tickers.
- **[Risk] The 55 threshold produces too many or no candidates in some regimes.** → Keep the threshold stable for initial implementation, record eligible/returned counts, and calibrate with evidence rather than auto-relaxation.
- **[Risk] Retiring `/actionable` breaks internal tools.** → Inventory and migrate frontend, diagnostics, guide, tests, and chat tools atomically; return a clear 404 after removal rather than a stale alias.

## Migration Plan

1. Reconcile/archive `refine-actionable-ranking` so its accepted useful helpers are the implementation baseline.
2. Extract a reusable live-transition selection surface without changing Setup Feed output; cover it with parity tests.
3. Implement and test the formation service and protected `/transitions/forming` endpoint alongside the existing actionable endpoint.
4. Add diagnostic parity and historical BE-like/DOCN-like replay fixtures; inspect score distributions and freeze component buckets.
5. Replace the dashboard component, place Setups Forming above the Setup Feed, update chat tools and guide copy, and verify loading/empty/error states.
6. Remove `/transitions/actionable` and dead actionable-only code after all repository consumers migrate.
7. Deploy backend and frontend together. Roll back both together to the previous release if formation/feed exclusivity or data health regresses; no database rollback is expected.

## Open Questions

- None required before implementation. A persistent transition-episode table is deliberately deferred unless shared live-selector parity proves impossible with current metrics/history.
