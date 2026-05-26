## 1. Backend — Empirical calculator skeleton

- [ ] 1.1 [empirical-probability] Create `backend/app/services/empirical_probability_calculator.py` with module docstring linking to this change, RS bucket constants (`_RS_BUCKETS`), the participation descriptor enum (`EXPANDING/STABLE/NARROWING/COLLAPSING/UNKNOWN`), and the `MIN_SAMPLE_SIZE = 5` constant
- [ ] 1.2 [empirical-probability] Define `EmpiricalLookupResult` dataclass with `probability: float`, `source: str` (`"empirical"` | `"rule_based"`), `sample_size: int`
- [ ] 1.3 [empirical-probability] Implement `EmpiricalProbabilityCalculator.__init__(db)` and helper `_rs_bucket(rs_value: float | None) -> str` returning one of the five bucket strings

## 2. Backend — Cohort lookup logic

- [ ] 2.1 [empirical-probability] Implement `_query_cohort(transition_type, rs_bucket=None, participation=None) -> (success, failure)` running a single GROUP BY on `transition_observations` returning counts of SUCCESS and FAILURE (NEUTRAL/PENDING/INSUFFICIENT_DATA excluded via WHERE clause)
- [ ] 2.2 [empirical-probability] Implement the fallback ladder in `lookup(transition_type, rs_value, participation_descriptor) -> EmpiricalLookupResult`:
  - Level 1: full cohort (all three keys)
  - Level 2: drop participation
  - Level 3: drop rs_bucket
  - Level 4: return rule-based sentinel (probability=0.0, source="rule_based", sample_size=0) — caller computes the formula
- [ ] 2.3 [empirical-probability] At each level, compute `success_rate = success / (success + failure)` only if `success + failure >= MIN_SAMPLE_SIZE`; otherwise fall through

## 3. Backend — Cache + invalidation

- [ ] 3.1 [empirical-probability] Add module-level `_cache: dict[tuple, tuple[EmpiricalLookupResult, datetime]]` keyed by the full triple (or sub-tuple); TTL = 600 seconds
- [ ] 3.2 [empirical-probability] Wire cache check at the start of `lookup()`; on hit within TTL, return cached
- [ ] 3.3 [empirical-probability] Add `EmpiricalProbabilityCalculator.clear_cache()` classmethod
- [ ] 3.4 [empirical-probability] Modify `backend/app/services/outcome_tracker.py` — at the end of `evaluate_pending()`, call `EmpiricalProbabilityCalculator.clear_cache()` inside try/except so outcome writes never fail because of cache issues

## 4. Backend — Rewire setup_lifecycle_engine

- [ ] 4.1 [setup-lifecycle] Modify `setup_lifecycle_engine.calculate_continuation_probability` signature: add optional `context: ParticipationDescriptor | None = None` parameter; return type changes from `float` to `tuple[float, str, int]`
- [ ] 4.2 [setup-lifecycle] Inside the method, instantiate the calculator (or accept it as a dep) and call `lookup(transition_type, rs_value, participation)`; if the result has `source == "empirical"`, return `(result.probability, "empirical", result.sample_size)`
- [ ] 4.3 [setup-lifecycle] On rule_based fallback, run the existing weighted-composite formula unchanged and return `(formula_result, "rule_based", 0)`
- [ ] 4.4 [setup-lifecycle] Determine the canonical `transition_type` string to pass to the lookup — match the value written into `transition_observations.transition_type` exactly (verify via inspection of `transition_engine.py`)

## 5. Backend — Endpoint contract updates

- [ ] 5.1 [empirical-probability] `backend/app/api/v1/endpoints/transitions.py`: where `continuation_prob` is set, unpack the tuple and add `probability_source` + `sample_size` to the response dict
- [ ] 5.2 [empirical-probability] `backend/app/api/v1/endpoints/queue.py`: same modification across all three lens endpoints (`ur-queue`, `emerging-leaders`, `building-bases`)
- [ ] 5.3 [empirical-probability] `backend/app/api/v1/endpoints/setup_lifecycle.py`: same modification at both call sites (lines ~60 and ~165 per current code)
- [ ] 5.4 [empirical-probability] Where market context is available cheaply, pass the participation descriptor as `context`; where it isn't (cold-path endpoints), pass `None` — calculator handles UNKNOWN

## 6. Backend — Validation

- [ ] 6.1 [empirical-probability] Curl `GET /api/v1/transitions/current` returns 200 with `probability_source` and `sample_size` present on every setup
- [ ] 6.2 [empirical-probability] Curl `GET /api/v1/queue/ur-queue` returns same — both fields on every entry
- [ ] 6.3 [empirical-probability] Verify a transition type with many historical observations returns `source: "empirical"` with sample_size > 5
- [ ] 6.4 [empirical-probability] Verify a rare transition type returns `source: "rule_based"` with `sample_size: 0`
- [ ] 6.5 [empirical-probability] Verify NEUTRAL outcomes are excluded: directly query DB for a cohort, count SUCCESS+FAILURE, compare to `sample_size` in API response
- [ ] 6.6 [empirical-probability] Verify cache: trigger `outcome_tracker.evaluate_pending()` (or simulate) and confirm next API call recomputes (log evidence)

## 7. Frontend — Source badge component

- [ ] 7.1 [empirical-probability] Modify `frontend/components/dashboard/CompactSetupCard.tsx` — add optional `probabilitySource?: 'empirical' | 'rule_based'` and `sampleSize?: number` props
- [ ] 7.2 [empirical-probability] Render badge near the `contPct` display: `empirical (N=42)` in muted color when source is empirical; `rule-based` in amber when rule_based; nothing when both props undefined (backward-compatible default)
- [ ] 7.3 [empirical-probability] Badge uses `text-[9px]` matching the existing freshness label scale; muted = `text-white/30`; amber = `text-amber-400/70`

## 8. Frontend — Wire pass-through

- [ ] 8.1 [empirical-probability] `frontend/components/dashboard/TopActionableSetups.tsx`: include `probability_source` and `sample_size` in the API response type; pass to `<CompactSetupCard>`
- [ ] 8.2 [empirical-probability] `frontend/components/dashboard/LiveTransitionFeed.tsx`: same pass-through
- [ ] 8.3 [empirical-probability] Check `frontend/components/queue/*` consumers of setup data and add pass-through where they render the probability
- [ ] 8.4 [empirical-probability] Visual smoke test in browser: at least one card shows `empirical (N=...)` and at least one shows `rule-based`

## 9. Frontend — Guide update

- [ ] 9.1 [empirical-probability] Add a new section to `frontend/app/guide/page.tsx` explaining: what the badge means, why N matters, why some cards say rule-based, and that the share will grow over weeks

## 10. Documentation + memory

- [ ] 10.1 [empirical-probability] Add module docstring to `empirical_probability_calculator.py` linking to this change directory
- [ ] 10.2 [empirical-probability] Update MEMORY.md with entry pointing to a new `empirical_probability_started.md` memory file
- [ ] 10.3 [empirical-probability] Create memory file `empirical_probability_started.md` (project type) noting: Phase 1 shipped, cohort key, min sample size, fallback ladder, NEUTRAL exclusion rationale, recalibration milestone (Aug 2026)

## 11. Spec archival

- [ ] 11.1 [empirical-probability] After 2-3 days of operator validation (use the new badge, confirm `empirical` share is non-zero and growing), run `openspec apply empirical-continuation-probability` to archive the change and promote/update specs
- [ ] 11.2 [empirical-probability] Confirm both the new `empirical-probability` spec and the modified `setup-lifecycle` spec land under `openspec/specs/`

## 12. Verification

- [ ] 12.1 [empirical-probability] End-to-end verification: take one cohort with ≥5 historical observations, count SUCCESS/FAILURE manually in the DB, compute success rate by hand, confirm the API returns the same number with matching sample_size
- [ ] 12.2 [empirical-probability] Backward-compatibility check: confirm no existing frontend page errors when the new fields are present (no required-prop violations, no missing-key warnings)
- [ ] 12.3 [empirical-probability] Performance check: cold-call latency on `/transitions/current` remains within 2× of pre-change baseline (empirical lookups are GROUP BY on indexed columns, should be negligible)
- [ ] 12.4 [empirical-probability] Operator validation (2-3 day soft window): Fernando uses the new badges in normal workflow, confirms empirical signal is informative and rule-based fallback is clear
