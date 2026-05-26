## Context

The current `MarketRegimeEngine` is a 329-line module that classifies the market
into a single enum (`risk_on/risk_off/transition/choppy`) using three static
metrics and four hardcoded thresholds. The conversation audit identified ten
specific anti-patterns; the two most material:

1. **"Leader" is `pullback_quality_score >= 60`** — a stock with -4% perf_1y
   and a technically pretty pullback counts as a leader. This inflates
   `leadership_health` and contaminates the final regime label.
2. **Choppy is the fallback bucket** — the code never *measures* chop. When no
   other rule matches, it returns choppy. This means "choppy" gives the
   operator no actionable information.

This change introduces a parallel engine with multi-dimensional output. The
two phases are clean: Phase 1 ships the framework + two engines as
proof-of-architecture; the other five engines come later. The legacy engine
stays running unchanged during Phase 1 so A/B comparison is possible without
breaking any existing consumer.

Data state at design time:
- `stock_metrics`: 22 distinct dates, avg 6 days/symbol, 6720 symbols
- `stock_prices`: 253 dates (1 trading year), 7007 symbols
- `is_quality_leader` returns ~399 stocks on latest date (6.5% of universe)
- SPY: 253 bars available; QQQ and RSP: NOT in `stock_prices`

## Goals / Non-Goals

**Goals:**

- Replace a single-label regime classification with a multi-dimensional
  behavior tablero, in a way that is honest about what is and isn't measured
- Establish `is_quality_leader` (Minervini SEPA) as the single source of
  truth for "leader" across the platform — same gate used by Setup Queue,
  Outcome Tracker, and now the context engine
- Ship a working endpoint + frontend swap that operators can use immediately
  while validating the new engine against their intuition
- Keep the architecture extensible: adding `forgiveness`, `persistence`, etc.
  in future phases must require zero changes to the dataclass framework or
  the API contract shape (only adding entries to the response and removing
  them from `engines_pending`)
- Maintain coherence with the seven non-negotiable principles, especially
  Principle 5 (regime affects everything) and Principle 7 (interpretability
  over prediction)

**Non-Goals:**

- Building all 7 engines now (5 of them are explicitly deferred to future
  phases — listed in `engines_pending`)
- Deleting `MarketRegimeEngine` or `/market-regime/current` (separate change
  after A/B validation)
- Composite numeric scores per engine (rejected by user; raw metrics +
  qualitative descriptor only)
- Operating posture rules (suppression/amplification of queue lenses) —
  requires the full 7-dimension framework
- Predictive elements — engine reports present observed state, not forecasts
- Calibrating descriptor thresholds against historical outcomes — deferred
  to August 2026 when `transition_observations` accumulates 90 days
- Adding `distance_to_low_52w_atr` as a precomputed column — Phase 1 uses
  `distance_to_high_52w_atr <= -6.0` as proxy
- Persisting engine output to a new table (in-memory cache only)
- Redis (in-memory dict with TTL is sufficient for Phase 1 load)

## Decisions

### 1. Parallel coexistence, not in-place replacement

The new engine lives at `backend/app/services/market_context_engine.py` with
its own endpoint `/api/v1/market-context/current`. The old engine and endpoint
remain untouched.

**Why:** atomic swap of the existing engine risks breaking consumers (the
`MarketStatusBar` reads it; `transitions.py:_calculate_priority_score`
indirectly uses regime). A separate deletion change can be small and confident
once the new context is validated. Coexistence cost is low: zero code in the
old path runs unless explicitly called.

### 2. `is_quality_leader` is the canonical leader definition

Phase 1 makes this binding via the spec. Any future consumer that wants to
identify "leaders" must use this gate.

**Why:** the old engine's `pullback_quality_score >= 60` definition is the
single most damaging bug in the conversation audit. Fixing it everywhere
requires anointing one canonical definition. The Minervini SEPA gate already
exists, is tested, and is used by `Setup Queue` and `Outcome Tracker`.

### 3. No composite score per engine — only raw metrics + descriptor

Each engine returns a dict of raw metrics + a single qualitative string
(`EXPANDING`, `THINNING`, etc.). No 0-100 number summarizing the engine.

**Why:** the user explicitly chose this in planning. Composite scores invite
comparisons across engines that aren't meaningful — comparing a 65 in
participation to a 65 in leadership creates false equivalence. The descriptor
forces interpretation by operator, which is the point.

### 4. Descriptors derived from explicit named thresholds, not magic numbers

All cutoffs live in module-level constants:

```python
_PARTICIPATION_THRESHOLDS = {
    'expanding':    +5.0,    # delta_5d > +5pp → EXPANDING
    'stable_min':   -5.0,    # -5pp ≤ delta_5d ≤ +5pp → STABLE
    'narrowing':   -15.0,    # -15pp ≤ delta_5d < -5pp → NARROWING
                              # below -15pp → COLLAPSING
}
_LEADERSHIP_THRESHOLDS = {
    'expanding':    +5.0,
    'thinning':     -5.0,
    'collapsing':  -15.0,
    'climactic_ratio_warn':  0.25,   # >25% climactic → EXHAUSTED override
    'extension_ratio_warn':  0.40,   # >40% extended → EXHAUSTED override
}
```

**Why:** the existing engine has thresholds like `0.65`, `0.40`, `0.20`
scattered through `_determine_regime` with no rationale. We name them, comment
them, and accept they'll need recalibration once we have 90 days of outcome
data (Aug 2026).

### 5. Historical comparisons use 7/14/28 calendar days as proxies for 5/10/20 trading days

Trading-day math requires a market calendar dependency. Calendar-day
approximation accepts that a Monday-Friday window crosses 7 calendar days;
the slight imprecision is acceptable for descriptor-level reporting (not for
backtests).

**Why:** zero new dependencies. The approximation is documented and bounded
(±2 days max drift across normal holiday weeks).

### 6. Universe used for deltas is the historical date's universe, not today's

When computing `breadth_above_ema21` 20 days ago, we apply `QUALITY_FILTERS`
to the rows at *that date*. A stock that was illiquid 20 days ago but qualifies
today does NOT retroactively enter the historical denominator.

**Why:** survivorship-bias prevention. Forcing today's filter retroactively
distorts derivatives. The cost is that universe size fluctuates day-to-day,
but this is honest and matches reality.

### 7. `delta_sample_size_20d` exposed in API response

The response includes the count of rows the 20-day delta operated over.
Operators can see when the data thins out.

**Why:** with only 22 days of `stock_metrics`, the 20-day window is currently
covered for ~50-60% of symbols. Hiding this would be dishonest. In 8 days
all symbols will have 20-day coverage and the field becomes informational
rather than gating.

### 8. Exhaustion overrides direction in leadership descriptor

A leadership set that's growing in count but where >25% of leaders are
climactic returns `EXHAUSTED`, not `EXPANDING`.

**Why:** top-of-trend signal. A market where leaders are expanding *and*
exhausting is a market about to roll over. Counting the expansion without
acknowledging the exhaustion is exactly the kind of retail thinking this
change is escaping from.

### 9. In-memory cache, keyed by `as_of` date, TTL ~5 minutes

A single module-level dict guards by `as_of`. On cache hit within TTL,
return cached. On `as_of` change (new trading day), invalidate.

**Why:** ~17 DB queries per cold call × 60s polling × 8h trading day = ~480
cold calls/day uncached. With 5-min TTL, ~100 cold calls/day — manageable.
Redis would be overkill for this load and adds an infra dependency we don't
have. Cache is process-local; if multiple uvicorn workers run, each holds
their own — acceptable for Phase 1.

### 10. Frontend ships as compact bar + expandable drawer

`MarketContextBar` is a two-line strip in the header. Click opens
`MarketContextDrawer` (slide-in from right) with the full tablero, the 9+10
raw metrics, and the `engines_pending` placeholder list.

**Why:** the dashboard has limited vertical space. The compact view
communicates the headline (descriptor + delta arrow); the drawer is for the
operator who wants to dig into "why is participation NARROWING right now?".

### 11. Atomic frontend swap, old component kept for rollback

`dashboard/page.tsx` imports the old `MarketStatusBar` today. The swap is a
one-line import change once the new components are ready. The old file is
NOT deleted — it stays on disk as escape hatch during the validation week.

**Why:** Phase 1 ships a new conceptual model. The operator (user) will need
2-3 days to validate it. Rollback being a single import revert is cheap
insurance.

### 12. Module structure: one file, multiple internal classes

`market_context_engine.py` contains: `ParticipationAnalysis`,
`LeadershipAnalysis`, `MarketContext` dataclasses + `MarketContextEngine`
class with private async methods per engine.

**Why:** ~300 LOC total, well under the 400-LOC decomposition threshold.
Splitting into separate files per engine premature given they share helpers
(`_universe_size`, `_count_where`, `_fetch_leaders`). When Phase 2 adds
forgiveness and persistence, if total LOC exceeds 400, decompose then.

## Risks / Trade-offs

### Risk 1: `stock_metrics` history depth (22 days) caps delta accuracy

**Impact:** `delta_20d` is unreliable for ~40-50% of universe today.

**Mitigation:**
- Report `delta_sample_size_20d` in API so consumer can judge confidence
- Engine degrades gracefully — returns `0.0` when no historical row exists
- Auto-resolves in ~8 days as `stock_metrics` accumulates coverage

**Accepted trade-off:** shipping with a known data-thin condition is
preferable to delaying 8 days. The descriptor still functions on 5d window
which has full coverage.

### Risk 2: `leadership_turnover_5d` may be noisy

A stock oscillating around the Minervini threshold (e.g., perf_1y crossing
30% repeatedly) inflates turnover artificially.

**Impact:** descriptor might flip between HEALTHY and THINNING day-to-day on
noise.

**Mitigation:**
- Turnover is reported as metric only; the descriptor depends on
  `delta_5d_pct`, not turnover
- If observed noise becomes operationally annoying, future change can require
  "leader for ≥2 consecutive days" (same pattern Setup Queue uses)

**Accepted trade-off:** Phase 1 doesn't add anti-noise filtering. Observe
behavior first.

### Risk 3: Descriptor thresholds are heuristic

The ±5pp / ±15pp cutoffs come from intuition, not calibration.

**Impact:** descriptor may not match operator's gut sense of "narrowing" vs
"collapsing".

**Mitigation:**
- Thresholds are named constants at top of module — easy to tune
- Recalibration is an explicit Aug 2026 milestone (when 90 days of
  `transition_observations` enables empirical threshold setting)
- Spec scenarios document expected behavior at each threshold — tuning is
  bounded by these scenarios

**Accepted trade-off:** shipping with documented heuristic thresholds beats
delaying for calibration we can't yet perform.

### Risk 4: 17 queries per cold call

**Impact:** uncached call ~1-2 seconds; if frontend polls every 60s and cache
fails, DB load increases.

**Mitigation:**
- In-memory cache with 5min TTL (Decision 9)
- Future change can add Redis if multiple workers + multi-user demand it
- Engine queries are simple counts/aggregates, indexed, fast

**Accepted trade-off:** no Redis dependency for Phase 1; revisit if observed
load warrants it.

### Risk 5: Operator confusion during transition period

Two engines reporting on the same dashboard during A/B can be confusing.

**Impact:** operator sees old "choppy" label alongside new "NARROWING /
THINNING" descriptors.

**Mitigation:**
- Compact bar is single source of truth in dashboard header
- Old `MarketStatusBar` removed from import the moment the new bar lands
- Old endpoint is preserved for API-level A/B, but UI shows only the new
- Operator validates by mental comparison, not by side-by-side UI

**Accepted trade-off:** the UI is unambiguous; backend coexistence is the
only "double engine" period and is invisible to the operator.

### Risk 6: QQQ / RSP not in `stock_prices`

**Impact:** future engines (rotation, follow_through) that want QQQ vs SPY
or equal-weight comparisons will need these ingested.

**Mitigation:**
- Phase 1 doesn't depend on QQQ/RSP
- Add ingestion as a precondition of the relevant future phase

**Accepted trade-off:** noted, not blocking Phase 1.

### Risk 7: `descriptor` string is API-breaking surface

If we add a new descriptor value in a future phase, consumers must handle it.

**Impact:** frontend must default-case unknown descriptors gracefully.

**Mitigation:**
- Frontend implementation defaults unknown descriptors to neutral styling
- Spec lists the exact enum values for each engine; expansion requires a
  spec delta in the future change

**Accepted trade-off:** standard enum-evolution discipline applies.
