## Context

The `continuation_probability` value displayed on every setup card across the
platform — `TopActionableSetups`, `LiveTransitionFeed`, and every Setup Queue
lens — is currently a hand-tuned weighted composite. Its four components
(weekly_trend_quality 40%, pullback_quality_score 30%, RS 20%, volume_contraction
10%) and the RS tier cutoffs (115/110/105/100/95) were chosen by intuition.
There is no record of these weights having been validated against any observed
outcomes. The number behaves like a score that operators read as a probability.

At the same time, `outcome_tracker` has been writing real outcomes to the
`transition_observations` table since the table was added. Every non-STABLE
transition is recorded with a full context snapshot (regime, RS, ADR, pullback
quality, weekly tightness, ATR — all at detection time), and after a 10-day
window the row is labeled `SUCCESS` / `FAILURE` / `NEUTRAL` /
`INSUFFICIENT_DATA` based on price movement and EMA21/EMA50 behavior.

The data is in the database. The number on the setup card does not consult it.
This change closes that loop.

State at design time:
- `transition_observations`: ~22 days of accumulated data, evaluation runs
  daily, exact row count per transition type varies
- Some transition types (RECLAIM_PREPARATION, UNDERCUT) likely have sub-10
  sample sizes per RS×regime cell
- `market-context-engine-phase-1` ships the `participation` descriptor that
  serves as the regime key for cohort stratification

## Goals / Non-Goals

**Goals:**

- Replace the synthetic continuation probability with an empirical frequency
  derived from `transition_observations` whenever a cohort with sufficient
  sample size exists.
- Make the source of the number transparent to the operator — every card
  shows whether the % came from observation (`empirical (N=42)`) or formula
  (`rule-based`).
- Use the `participation` descriptor from `market-context-engine-phase-1` as
  a cohort key, making this change the first concrete consumer of market
  context inside another engine (Principle 5).
- Keep the rule-based formula as the fallback, untouched, so the system
  degrades gracefully when cohorts are sparse.
- Establish a fallback ladder that prevents sparse-data overconfidence
  without hiding the fallback from the operator.

**Non-Goals:**

- Bayesian smoothing, beta-binomial priors, Wilson intervals — Phase 1 is a
  stratified frequency, period. If operators want intervals later, that's a
  separate change.
- Replacing or recalibrating the rule-based formula weights — they remain as
  the fallback. Recalibration is the August 2026 milestone, jointly with the
  market-context descriptor thresholds.
- Multi-class outcomes — only binary SUCCESS/FAILURE enter the success-rate
  denominator. NEUTRAL is explicitly excluded.
- Recency weighting / sliding-window decay — all observations carry equal
  weight in Phase 1. Drift mitigation comes from including the participation
  descriptor in the cohort key.
- A drill-down UI showing per-cohort matrices — Phase 1 surfaces source +
  sample size only.
- Backfilling missed `outcome_tracker` evaluations.
- Redis-backed shared cache across uvicorn workers — per-process in-memory
  cache is sufficient for Phase 1 load.
- Outcome write-time per-cohort cache invalidation — Phase 1 clears the whole
  cache on outcome writes; per-key invalidation can come later if needed.

## Decisions

### 1. NEUTRAL is excluded from both numerator and denominator

A `NEUTRAL` outcome means the setup neither clearly succeeded nor clearly
failed within the evaluation window. Treating it as a failure inflates the
failure rate and misrepresents the data; treating it as a success does the
opposite. The honest move is to exclude it from the success-rate calculation
entirely:

```
success_rate = COUNT(SUCCESS) / COUNT(SUCCESS) + COUNT(FAILURE)
```

`PENDING` and `INSUFFICIENT_DATA` are also excluded — they represent
not-yet-evaluated or unevaluable observations.

**Why:** The operator should not be told that a transition with 5 SUCCESS, 0
FAILURE, and 10 NEUTRAL has a 33% success rate. It has a 100% success rate
on a sample of 5, which is exactly what we report (and the small sample is
itself flagged via the sample_size field).

### 2. Cohort key is `(transition_type, rs_bucket, participation_descriptor)`

These three are the highest-leverage stratifications:
- **transition_type** is the primary axis — different transitions have
  fundamentally different base rates
- **rs_bucket** captures the strength tier of the underlying stock — RS 95
  setups behave differently than RS 120 setups
- **participation_descriptor** captures market context — same setup behaves
  differently when breadth is EXPANDING vs COLLAPSING

ADR, sector, market cap, and other dimensions are deliberately NOT in the
key. Adding more dimensions deepens the cohort and shrinks each cell — at
22 days of data even three dimensions is aggressive. Future phases can add
dimensions as data accumulates.

### 3. Five-observation minimum sample threshold

Below five `SUCCESS + FAILURE` observations, the cohort is treated as too
sparse and the fallback ladder drops one dimension and retries.

**Why:** five is small enough to start using empirical data early in the
data-collection lifecycle without being so small that one or two outcomes
dominate. A 4-of-5 cohort still reports 80% — wrong direction would be
reporting empirical with N=2. The sample_size field exposes the denominator,
so an operator who wants to ignore N<10 results can do so visually.

### 4. Explicit three-level fallback ladder

```
Level 1: (transition_type, rs_bucket, participation_descriptor)
Level 2: (transition_type, rs_bucket)
Level 3: (transition_type,)
Level 4: rule-based formula
```

Each level is tried in order; the first level meeting the sample threshold
wins. The system never silently picks a higher level — the chosen level is
reflected only in the resulting sample_size.

**Why:** the ladder drops the most sparse-prone dimensions first. The
participation descriptor splits four ways, the RS bucket splits five ways —
combined they multiply cell count by 20. Dropping participation first
recovers the most data. Dropping RS second still preserves transition
type, which is the most important axis.

**Decision:** the source flag in the response is `"empirical"` for Levels
1-3 (all three are observations) and `"rule_based"` only for Level 4. We do
NOT expose which level was used as a distinct enum — the sample_size and
the natural shrinkage of cell sizes communicate that implicitly. Operators
who need that detail can drill down via the (future) cohort inspection view.

### 5. Cache invalidation hooks into `outcome_tracker` writes

When `outcome_tracker.evaluate_pending()` writes new outcome rows, it calls
`EmpiricalProbabilityCalculator.clear_cache()` before returning. The cache
also has a 10-minute TTL as a backstop.

**Why:** the cache is reading historical outcome data. The only event that
changes that data is a new outcome write. Tying invalidation to that event
keeps reads cheap and writes correct, without polling or generation counters.
Phase 1 clears the whole cache on any write (coarse but simple); per-cohort
invalidation can come later if the cache grows large enough to matter.

### 6. Per-process in-memory cache, not Redis

Same trade-off as `market-context-engine-phase-1` Decision 9. Lookups are
fast (single GROUP BY query over an indexed column), the cache is the load
shield. Multiple uvicorn workers each maintain their own — acceptable since
the data only changes on outcome evaluation, which is bounded.

### 7. API contract adds metadata, does not change the probability field

The float in `[0.0, 1.0]` keeps its name and range. Two sibling fields appear:
`probability_source: "empirical" | "rule_based"` and `sample_size: int`. Any
consumer that ignored the new fields would continue working — the contract
*requirement* is that they are always present, so consumers can rely on them.

**Why:** the alternative (replacing the float with a nested object) would
break every existing consumer. The chosen shape is additive and backward-
compatible in practice, while still being a spec-level contract change
because the meaning of "continuation probability" now formally includes its
source.

### 8. Bootstrap fallback: rule-based, never synthetic empirical

For transition types with zero history (a future new transition type, or
during cold-start), the lookup returns `(rule_based, 0)`. The rule-based
formula evaluates and its output becomes the probability. The system never
fabricates an "empirical" number from less than the threshold.

**Why:** the entire point of the change is honesty about what the number
represents. A "fake empirical" with sample size 1 would be worse than no
change at all.

### 9. RS bucket cutoffs match the existing rule-based RS tier

The four buckets (`lt_100`, `100_110`, `110_120`, `gte_120`) mirror the
existing RS tiering in the rule-based formula, plus an `unknown` bucket for
NULL RS. This keeps the two systems aligned conceptually and means an
operator who knows the rule-based weights can predict which cohort bucket a
setup will land in.

**Why:** parallel structure between fallback and empirical reduces cognitive
load. There's no good reason to invent different cutoffs.

### 10. Frontend badge is the contract surface for transparency

The badge on the setup card is what makes the change real to the operator. A
backend-only change would be invisible. The badge styling is intentionally
contrasted: muted for empirical (don't distract), amber for rule-based
(flag the synthetic origin without making it scary).

**Why:** if operators can't distinguish empirical from synthetic at a
glance, the trust improvement does not happen. The badge is the proof.

## Risks / Trade-offs

### Risk 1: Sparse data leads to confident-but-wrong empirical numbers

**Impact:** with 22 days of data, even Level 3 cohorts may have N=5–10.
Reporting "empirical 80% (N=5)" is technically accurate but easy for the
operator to over-weight.

**Mitigation:**
- `sample_size` is part of the API contract — always visible
- Frontend badge shows `(N=5)` explicitly so the small denominator is in
  the operator's line of sight
- Threshold of 5 is the minimum, not the target — most cohorts will grow
  beyond it within weeks

**Accepted trade-off:** shipping with N≥5 is more valuable than waiting
months for N≥30. The transparency mitigates the rest.

### Risk 2: Regime drift contaminates empirical history

**Impact:** an observation from 60 days ago in EXPANDING participation may
not predict behavior in today's NARROWING participation.

**Mitigation:**
- `participation_descriptor` is part of the cohort key, so EXPANDING-era
  observations are isolated from STABLE-era observations
- The Level 1 cohort partitions by regime explicitly
- Recency weighting (sliding window or exponential decay) is deferred to
  Phase 2

**Accepted trade-off:** regime as cohort key is a structural fix; recency
weighting is an optimization on top. Phase 1 takes the structural fix only.

### Risk 3: NEUTRAL exclusion may overstate apparent success rate

**Impact:** a transition type that resolves to NEUTRAL frequently (a
genuinely ambiguous transition) gets reported on the small subset that
resolved cleanly. A cohort with 2 SUCCESS, 0 FAILURE, 20 NEUTRAL reports
100% on N=2.

**Mitigation:**
- The 5-observation threshold rejects the N=2 case → falls through ladder
- Exposing `sample_size` means N=5 with 20 NEUTRAL excluded is visible to
  the operator
- Future change can add a `neutral_rate` sibling field if operators ask for
  it

**Accepted trade-off:** the exclusion is the honest computation. The
threshold + visibility together address the inflation risk.

### Risk 4: Bootstrap problem — first-day deployment shows mostly rule-based

**Impact:** on day 1, most cohorts won't meet the threshold and most cards
show `rule-based`. Operator perception: "this change does nothing".

**Mitigation:**
- Document this expectation in the launch note: empirical share grows over
  weeks as observations accumulate and evaluation completes
- The badges that DO show `empirical` early are themselves proof the system
  works
- Within 4–6 weeks, common transition types should cross the threshold for
  most cohort levels

**Accepted trade-off:** the slow ramp is honest. Faking it would defeat
the change.

### Risk 5: Cache invalidation hook coupling

**Impact:** modifying `outcome_tracker` to call into the empirical
calculator creates a hard dependency between the two services. If the call
fails, outcomes still write but the cache stays stale (up to 10 min TTL).

**Mitigation:**
- The hook is wrapped in try/except — outcome writing never fails because
  of a cache miss
- TTL backstop ensures eventual freshness even if hooks fail silently
- Tests verify both the hook fires and the TTL works

**Accepted trade-off:** the coupling is intentional and minimal (one
function call); the failure mode is graceful (slightly stale reads).

### Risk 6: Frontend pass-through churn

**Impact:** every consumer of `CompactSetupCard` needs to pass the two new
fields through. Easy to miss one, leaving a card with no badge.

**Mitigation:**
- TypeScript optional props default to a clear "unknown" badge rendering
- The contract spec requires the fields on every endpoint — frontend tests
  catch missing fields
- Validation step in tasks includes manual inspection of every consumer

**Accepted trade-off:** prop drilling is the cost of Phase 1's contract
shape. A context provider could be added later if pass-through becomes a
maintenance burden.

### Risk 7: Source flag conflated with sample size

**Impact:** operators may treat `empirical (N=5)` and `empirical (N=200)`
as equivalent because both say "empirical".

**Mitigation:**
- The sample size is rendered with the badge — N=5 visually differs from N=200
- Operator guide (in `/guide`) explains the meaning of sample size

**Accepted trade-off:** the alternative — hiding sample size — would be
strictly worse.
