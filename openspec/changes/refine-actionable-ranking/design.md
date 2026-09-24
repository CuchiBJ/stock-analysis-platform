## Context

The actionable endpoint has its own four-part score: pullback quality 40%, freshness 25%, regime alignment 20%, and leader quality 15%. The last component currently repeats pullback quality. Daily `relative_strength_spy` values already exist in `stock_metrics`, are produced by the normal metrics ingestion path, and are used elsewhere to calculate RS momentum over historical sessions.

The shared `_INSTITUTIONAL_SETUP` expression is also used by the live feed. Removing its near-high predicate in place would silently loosen both products, which is outside this change.

## Goals / Non-Goals

**Goals:** make actionable eligibility continuous with its graded quality score; give the 15% component an independent, explainable leadership meaning; preserve live, breakout, structural, regime, and deterioration protections.

**Non-goals:** new data sources, fundamental proxies, ML, general scoring-engine consolidation, or changes to other queues.

## Decisions

### D1: Split actionable and live structural filters

Define a shared institutional base containing market-cap, liquidity, volatility, price, performance, moving-average, and 52-week-low protections. The actionable filter uses that base plus its EMA9/EMA21 trigger. The live filter adds `distance_to_high_52w_atr >= -3.0` before applying its own transition logic.

Breakout surfacing remains stricter: EMA21 distance must be `(0, 1.5]` ATR and 52-week-high distance must be at least `-1.0` ATR.

### D2: Keep 52-week-high distance graded in pullback quality

No new distance score is introduced. The existing pullback-quality buckets remain authoritative: 20 points at >= -1 ATR, 15 at >= -2, 10 at >= -3, 5 at >= -4, and 0 below -4 or when missing. This avoids double counting and preserves the operator-visible breakdown.

### D3: RS-during-pullback replaces the duplicated 15%

Use the current and five-market-session-prior `relative_strength_spy` values:

- Level score (60%): RS >=110 => 100; >=105 => 80; >=100 => 60; >=95 => 40; otherwise 20.
- Trend score (40%): five-session percentage change >=2% => 100; >=0.5% => 80; >-0.5% => 60; >-2% => 30; otherwise 0.
- Component = `0.60 * level_score + 0.40 * trend_score`.
- Missing current/baseline data or a zero baseline => 50 neutral.

The endpoint delegates to `backend/app/services/actionable_ranking.py`, which fetches one baseline date and all candidate values in bulk and calculates the pure score. The breakdown exposes current RS, baseline RS, percentage delta, level score, trend score, and status (`improving`, `stable`, `deteriorating`, or `missing_history_neutral`).

### D4: Do not add fundamental acceleration

The stock and metrics schemas contain no reliable fundamental acceleration fields, and ingestion contains no earnings/revenue/EPS acceleration pipeline. A price-performance proxy would duplicate technical momentum and mislabel it as fundamentals. The RS component therefore fills the full 15% replacement.

## Risks / Trade-offs

- A larger candidate pool can increase ranking work, bounded by the existing pre-sort limit of 50 and final top-N cap.
- Five sessions can be noisy; discrete buckets and the 60% absolute-level weight prevent a single short-term move from dominating.
- A candidate with missing historical RS receives a neutral 7.5 percentage-point contribution. This avoids both data-gap exclusion and accidental promotion.
- The endpoint module is already large; this change extracts the new data/scoring logic into a focused service while leaving broader endpoint decomposition outside scope.

## Verification

- Compile both SQL expressions to prove the near-high predicate is absent from actionable and present in live.
- Test the exact breakout -1.0/-1.01 boundary.
- Test actionable/live diagnostics with `distance_to_high_52w_atr=-4.39`.
- Unit-test all RS trend states and missing history.
- Run the relevant backend test files, then the broader backend suite and frontend typecheck if available.
