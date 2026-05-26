## Why

The current `MarketRegimeEngine` reduces market state to a single retail-style
label (`risk_on/risk_off/transition/choppy`) derived from three static
snapshots. Operationally this is wrong on multiple levels: it classifies
"choppy" by elimination rather than measurement, it inflates `leadership_health`
by defining "leader" as a technical pullback score instead of Minervini SEPA,
its `speculative_appetite` metric is dominated by the `QUALITY_FILTERS` floor
(noise, not signal), and it has no derivatives — a market deteriorating from
60% → 47% breadth looks identical to one improving from 30% → 47%.

The operator needs to read **market behavior**, not market direction. A bullish
choppy market exists. An index trending up with collapsing leadership exists.
Single-label classification systematically hides these states and produces
false confidence. Principle 5 ("regime affects everything") becomes harmful
when the regime signal itself is unreliable.

This change introduces a multi-dimensional context engine as proof-of-architecture
for the 7-dimension behavior framework, starting with the two most foundational
dimensions: participation and leadership quality.

## What Changes

- **New module** `backend/app/services/market_context_engine.py` exposing a
  `MarketContextEngine` that returns a `MarketContext` dataclass with two
  sub-analyses (`participation`, `leadership`) plus an `engines_pending` list
  declaring the 5 dimensions reserved for future phases.

- **Participation engine** computes 9 raw metrics from current `stock_metrics`
  + historical comparisons (5d, 20d). Output includes a qualitative descriptor:
  `EXPANDING / STABLE / NARROWING / COLLAPSING`. NO composite score.

- **Leadership quality engine** computes 10 raw metrics. **The canonical
  definition of "leader" migrates from `pullback_quality_score >= 60` to
  `quality_leader_gate.is_quality_leader` (8 Minervini SEPA criteria)** —
  this is the most material conceptual fix in the change. Descriptor:
  `EXPANDING / HEALTHY / THINNING / COLLAPSING / EXHAUSTED`.

- **New endpoint** `GET /api/v1/market-context/current` returning the full
  multi-dimensional structure. Cached in-memory ~5min TTL.

- **Old `/market-regime/current` endpoint preserved unchanged** during this
  phase to enable A/B validation. Deletion of the old engine + endpoint is a
  separate change after consumers migrate.

- **Frontend swap**: `MarketStatusBar` (compact regime label) replaced in
  `dashboard/page.tsx` by new `MarketContextBar` (compact two-line layout) +
  `MarketContextDrawer` (expandable full tablero). Old component file kept on
  disk for rollback during validation; deleted in follow-up change.

- **NO new tables, NO migrations.** Uses existing `stock_metrics` history
  (currently 22 calendar days) and applies `QUALITY_FILTERS` consistently.

## Non-Goals

- **The other 5 behavior engines** (persistence, forgiveness, rotation,
  volatility, follow_through) are explicitly out of scope. They come in future
  phases as named in the response shape's `engines_pending` field.

- **Operating posture rules** (suppression/amplification of queue lenses based
  on context) — requires all 7 dimensions, deferred.

- **Composite "market context score"** as a single number — explicitly
  rejected. Single labels are exactly what this change is escaping from.

- **Deletion of `MarketRegimeEngine` and `/market-regime/current`** — separate
  follow-up change after A/B validation period.

- **Predictive elements** — engine reports current observed state only. No
  forecasting of next regime.

- **Threshold recalibration against historical outcomes** — deferred to August
  2026 when `transition_observations` has 90 days of accumulated outcomes.

- **`distance_to_low_52w_atr` precomputed metric** — Phase 1 uses
  `distance_to_high_52w_atr <= -6.0` as proxy for "near 52w low". Precision
  upgrade deferred to separate change if needed.

## Capabilities

### New Capabilities

- `market-context`: Multi-dimensional behavior-based market read. Defines the
  vector of orthogonal dimensions (participation + leadership in Phase 1;
  framework reserves persistence, forgiveness, rotation, volatility,
  follow_through for future phases), the canonical definition of "leader" via
  Minervini SEPA gate, the descriptor taxonomies per engine, the explicit
  rejection of single-label regime classification, and the API contract for
  the `/market-context/current` endpoint.

### Modified Capabilities

(None. The existing `market-regime` capability remains unchanged in this phase.
Its deletion or modification will happen in a separate change after the new
`market-context` capability is validated against real operator use.)

## Impact

**Defends principle:** Principle 5 (regime affects everything) — by making the
regime signal itself trustworthy. Also Principle 7 (interpretability over
prediction) — multi-dimensional descriptors are more interpretable than a
single opaque label.

**Code:**
- NEW: `backend/app/services/market_context_engine.py` (~300 LOC estimated)
- NEW: `backend/app/api/v1/endpoints/market_context.py` (~50 LOC)
- MODIFIED: `backend/app/api/v1/api.py` (one line: register new router)
- NEW: `frontend/components/dashboard/MarketContextBar.tsx`
- NEW: `frontend/components/dashboard/MarketContextDrawer.tsx`
- MODIFIED: `frontend/app/dashboard/page.tsx` (swap import after components ready)

**APIs:**
- ADDED: `GET /api/v1/market-context/current`
- UNCHANGED: `GET /api/v1/market-regime/current` (preserved for A/B)

**Dependencies:**
- Reuses `quality_leader_gate.is_quality_leader` (no changes to this module)
- Reuses `universe_filters.QUALITY_FILTERS` (no changes)
- Reuses existing `stock_metrics` schema (no migration)

**Risks (detailed in design):**
1. `stock_metrics` only has 22d history — 20d deltas valid for ~50-60% of
   universe; response must include `delta_sample_size_20d` for honesty
2. `leadership_turnover_5d` may be noisy from symbols oscillating around the
   Minervini threshold day-to-day
3. Descriptor cutoffs are heuristic (-5pp / -15pp) and must be documented
   explicitly in code, not buried as magic numbers
4. ~17 queries per refresh → cache TTL is load-bearing (no Redis available)
