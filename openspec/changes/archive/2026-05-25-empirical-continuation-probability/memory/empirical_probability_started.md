---
name: empirical-probability-started
description: Phase 1 of empirical continuation probability shipped — cohort key, fallback ladder, cache strategy, NEUTRAL exclusion
metadata:
  type: project
---

Empirical continuation probability Phase 1 shipped 2026-05-24.

**Core facts:**
- New service: `backend/app/services/empirical_probability_calculator.py`
- Cohort key Phase 1: `(transition_type, rs_bucket)` — participation dimension skipped because `regime_at_detection` stores old choppy/risk_on labels, not new participation descriptors
- MIN_SAMPLE_SIZE = 5; below threshold falls through fallback ladder
- Fallback ladder: (transition_type, rs_bucket) → (transition_type,) → rule_based sentinel
- NEUTRAL outcomes excluded from both numerator and denominator — honest exclusion of ambiguous outcomes
- Cache: per-process in-memory dict, TTL = 600 s, cleared on every `evaluate_pending_outcomes()` write
- RS buckets: lt_100 / 100_110 / 110_120 / gte_120 / unknown (match existing rule-based RS tiers)

**API contract change:**
Every endpoint returning `continuation_probability` now also returns:
- `probability_source`: "empirical" | "rule_based"
- `sample_size`: int (0 when rule_based)

**Frontend:**
- `CompactSetupCard` shows badge below the % — muted white for empirical (N=…), amber for rule_based
- `TopActionableSetups` passes through new fields

**Why:** The continuation_probability was a synthetic heuristic formula with no validation. The DB has 22 days of real outcome data. This change closes the loop by using observed success rates when cohort is large enough. The badge is what makes the change visible to the operator.

**Recalibration milestone:** August 2026 — recalibrate rule-based weights and participation thresholds against accumulated transition_observations data.

**Known limitation:** Phase 1 will mostly show rule_based (sparse cohorts with 22 days of data). Empirical share will grow as outcome evaluations accumulate over weeks.

**Why** — [[market_context_started]] ships the participation descriptor that would be Level 1 cohort key, but `regime_at_detection` in `transition_observations` stores old labels. Adding `participation_at_detection` column is deferred to a future change.

**How to apply:** When adding new transition types or modifying outcome evaluation logic, verify that `transition_type` values written to `transition_observations` match what's passed to `EmpiricalProbabilityCalculator.lookup()`.
