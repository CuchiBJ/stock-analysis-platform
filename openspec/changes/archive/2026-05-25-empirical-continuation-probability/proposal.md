## Why

Every setup card on the platform displays a "continuation probability %" that
operators reasonably interpret as a probability. It is not. It is a hand-tuned
weighted sum of four metrics (weekly_trend_quality × 0.40 +
pullback_quality_score × 0.30 + RS bucket × 0.20 + volume_contraction × 0.10)
that has never been validated against a single observed outcome.

Meanwhile, the `transition_observations` table has accumulated 22+ days of
actual outcome data — `SUCCESS / FAILURE / NEUTRAL` labels per detected
transition, with full context snapshots (regime, RS, ADR, pullback quality at
detection). The data exists, no consumer reads it, and the number that drives
operator decisions remains synthetic. This violates Principle 9 (institutional
sponsorship is primary signal — and sponsorship is empirical, not formulaic)
and is the audit's Priority 2 unfinished work: "make the signal real, not
synthetic". Phase 1 of `market-context-engine` already did this for the regime
label; this change does the equivalent for the per-setup probability.

## What Changes

- **NEW capability** `empirical-probability`: stratified-cohort success-rate
  lookups from `transition_observations`, with explicit fallback ladder when
  sample size is insufficient.

- **NEW service** `backend/app/services/empirical_probability_calculator.py`
  exposing `EmpiricalProbabilityCalculator.lookup(transition_type, rs_value,
  participation_descriptor) → (probability, sample_size, source)`. Cohort key
  is `(transition_type, rs_bucket, participation_descriptor)`; fallback drops
  participation first, then rs_bucket, returning `None` if no level has the
  minimum sample size.

- **MODIFIED** `setup_lifecycle_engine.calculate_continuation_probability()`:
  tries empirical lookup first; falls back to the existing rule-based formula
  ONLY when empirical sample size is below threshold. Returns
  `(probability, source, sample_size)` instead of a bare float.

- **BREAKING API contract**: all endpoints returning `continuation_probability`
  (`/transitions/current`, `/queue/*`, `/setup-lifecycle/*`) ADD two
  sibling fields: `probability_source: "empirical" | "rule_based"` and
  `sample_size: int`. The probability number itself remains the same field and
  range — only metadata is added. Existing consumers ignoring the new fields
  continue to work; the contract change is the spec promise that they will
  always be present.

- **MODIFIED** frontend: `CompactSetupCard` and the two consumers that render
  it (`TopActionableSetups`, `LiveTransitionFeed`) display a small badge below
  the % showing `empirical (N=42)` in muted text OR `rule-based` in amber when
  fallback is used. Transparency is the entire point — operator must know when
  a number is measured vs computed.

- **NEW in-memory cache** for cohort lookups keyed by `(transition_type,
  rs_bucket, participation_descriptor)`, TTL ~10 min. Invalidated explicitly
  when `outcome_tracker` writes new outcome rows (hook in the existing tracker,
  no new background process).

- **NO new tables, NO migrations, NO new dependencies.**

## Non-Goals

- **Confidence intervals, Bayesian smoothing, or posterior distributions** —
  Phase 1 returns a stratified frequency, full stop. Beta-binomial or Wilson
  intervals are deferred to a separate change once operators ask for them.
- **Replacing the rule-based formula** — it stays as the fallback while
  empirical history accumulates and for cohorts that never have enough samples
  (rare transition types).
- **Multi-class outcomes** — only binary `SUCCESS / FAILURE` enters the
  success-rate denominator. `NEUTRAL` is explicitly excluded (a setup that
  goes nowhere is neither a win nor a loss).
- **A drill-down UI showing per-cohort breakdowns** — operator can see the
  badge with sample size; the full cohort matrix view is a future change.
- **Backfilling missed outcome evaluations** — consumes only what
  `outcome_tracker` has already written.
- **Recency weighting / sliding-window decay** — Phase 1 treats all
  observations equally. Drift mitigation comes from regime being part of the
  cohort key, not from time-weighting.
- **Calibration plots, reliability diagrams, brier scores** — these belong in
  a validation/analytics change once 90+ days of outcomes exist (August 2026
  recalibration milestone, same as market-context thresholds).
- **Changing the rule-based formula weights** — the formula remains the
  fallback, untouched. This change wraps it, doesn't replace it.

## Capabilities

### New Capabilities

- `empirical-probability`: stratified-cohort empirical success-rate engine.
  Defines the cohort key structure, the fallback ladder, the minimum sample
  size threshold, the explicit handling of `NEUTRAL` outcomes, the cache
  invalidation contract with `outcome_tracker`, and the API surface
  (`probability_source`, `sample_size`) that every continuation-probability
  endpoint MUST expose.

### Modified Capabilities

- `setup-lifecycle`: `calculate_continuation_probability` changes its return
  signature from `float` to a tuple `(probability, source, sample_size)`. The
  *behavior* of the rule-based path is unchanged — it just becomes a documented
  fallback rather than the only implementation. This is a spec-level change
  because the contract for what "continuation probability" means now includes
  the source of the number.

## Impact

**Defends principles:**

- Principle 7 (interpretability over prediction) — an empirical frequency from
  named observable cohorts is more interpretable than a hardcoded weighted sum.
- Principle 5 (regime affects everything) — regime (via participation
  descriptor) becomes a cohort key, making this the first concrete consumer of
  market-context data inside another engine.
- Principle 9 (institutional sponsorship is primary signal) — measuring what
  actually happens to historical transitions IS sponsorship measurement.

**Code:**

- NEW: `backend/app/services/empirical_probability_calculator.py` (~150 LOC est.)
- MODIFIED: `backend/app/services/setup_lifecycle_engine.py`
  (~30 LOC change in `calculate_continuation_probability` + signature update)
- MODIFIED: `backend/app/services/outcome_tracker.py`
  (~5 LOC: cache-invalidation hook after writing outcomes)
- MODIFIED: `backend/app/api/v1/endpoints/transitions.py` (response shape +2 fields)
- MODIFIED: `backend/app/api/v1/endpoints/queue.py` (response shape +2 fields)
- MODIFIED: `backend/app/api/v1/endpoints/setup_lifecycle.py` (response shape +2 fields)
- MODIFIED: `frontend/components/dashboard/CompactSetupCard.tsx` (source badge)
- MODIFIED: `frontend/components/dashboard/TopActionableSetups.tsx` (pass through)
- MODIFIED: `frontend/components/dashboard/LiveTransitionFeed.tsx` (pass through)
- MODIFIED: `frontend/components/queue/*` consumers as needed (pass through)

**APIs:**

- ADDED to responses: `probability_source`, `sample_size` on every endpoint
  that previously returned `continuation_probability` (or `continuation_prob`).
- UNCHANGED: the probability value range (0.0–1.0) and the field name.

**Dependencies:**

- Reuses `MarketContextEngine` (participation descriptor as cohort key)
- Reuses `outcome_tracker` (cache invalidation hook only — no logic changes)
- Reuses `TransitionObservation` model (read-only)
- No new packages.

**Risks (detailed in design):**

1. Sparse-data overconfidence with only 22 days of observations → cohort
   fallback ladder is the mitigation.
2. Regime drift contaminating older observations → regime as cohort key is
   the Phase 1 mitigation; recency weighting deferred.
3. `NEUTRAL` exclusion can inflate apparent success rate for genuinely
   ambiguous transitions → spec mandates exposing `sample_size` so operator
   sees the denominator.
4. Bootstrap problem: transition types with zero data → fall back to
   rule-based, never return synthetic empirical numbers.
5. Cache staleness across uvicorn workers → in-memory cache is per-process,
   acceptable for Phase 1 load; Redis deferred.
