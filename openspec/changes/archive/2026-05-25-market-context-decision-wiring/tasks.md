## 1. Backend — Context decision filter core

- [ ] 1.1 [context-decision-filter] Create `backend/app/services/context_decision_filter.py` with module docstring linking to this change directory
- [ ] 1.2 [context-decision-filter] Define `ContextMultiplier` dataclass with fields `score_multiplier: float`, `suppress_lenses: list[str]`, `surface_warnings: list[str]`
- [ ] 1.3 [context-decision-filter] Define module-level `_NEUTRAL` constant `ContextMultiplier(1.0, [], [])` returned for any UNKNOWN / unmatched combination
- [ ] 1.4 [context-decision-filter] Define `_RULES` table — Python dict literal containing exactly the cells from the spec (COLLAPSING participation, NARROWING × adverse leadership, EXHAUSTED leadership override, EXPANDING × supportive leadership)
- [ ] 1.5 [context-decision-filter] Define `_REASONS` table — `dict[tuple[str, str], str]` keyed by `(participation, leadership)` returning the Spanish suppression-reason sentence used by queue endpoints
- [ ] 1.6 [context-decision-filter] Implement `compute_context_multiplier(participation, leadership) -> ContextMultiplier` — coerces any invalid value to UNKNOWN, consults _RULES with COLLAPSING > NARROWING+adverse > EXHAUSTED override > EXPANDING boost precedence
- [ ] 1.7 [context-decision-filter] Implement `format_suppression_reason(lens, participation, leadership) -> str` returning the human-readable Spanish reason or a default

## 2. Backend — Cache layer

- [ ] 2.1 [context-decision-filter] Add module-level `_cache: dict[tuple[str, str], tuple[ContextMultiplier, datetime]]`, TTL = 300 s
- [ ] 2.2 [context-decision-filter] Wire cache check at start of `compute_context_multiplier()`; cache hit within TTL returns cached
- [ ] 2.3 [context-decision-filter] Add `clear_cache()` classmethod/function for future invalidation hooks

## 3. Backend — Endpoint integration helper

- [ ] 3.1 [context-decision-filter] Add `async def fetch_current_context(db) -> tuple[str, str]` helper: calls `MarketContextEngine`, returns `(participation_descriptor, leadership_descriptor)` strings, gracefully returns `("UNKNOWN", "UNKNOWN")` on any exception (cold-start safety)
- [ ] 3.2 [context-decision-filter] Add INFO logging inside `fetch_current_context` exception path so silent fallbacks remain visible

## 4. Backend — transitions.py /actionable wiring

- [ ] 4.1 [setup-lifecycle] Modify `backend/app/api/v1/endpoints/transitions.py:get_actionable_setups` to call `fetch_current_context(db)` once at top of try block, before the loop
- [ ] 4.2 [setup-lifecycle] Call `compute_context_multiplier(participation, leadership)` once and reuse the result for every setup
- [ ] 4.3 [setup-lifecycle] Apply `context.score_multiplier` to `priority_score` (still bounded by existing `min(1.0, ...)` clamps where present)
- [ ] 4.4 [setup-lifecycle] Add `context_warnings` field to each setup dict, populated from `context.surface_warnings`
- [ ] 4.5 [setup-lifecycle] Change the return shape from `actionable[:limit]` (bare list) to `{"context_snapshot": {...}, "setups": actionable[:limit]}` — wrap in object
- [ ] 4.6 [setup-lifecycle] Confirm regression: existing `_REGIME_CONT_MULT` continues to apply (do not remove it — composition is intentional per design Decision 4)

## 5. Backend — queue.py lens wiring

- [ ] 5.1 [context-decision-filter] In `backend/app/api/v1/endpoints/queue.py`, factor out a small helper `_with_context_envelope(lens_id, results, context)` that wraps any list result into `{"suppressed": bool, "suppression_reason": str | None, "context_snapshot": {...}, "results": [...]}`
- [ ] 5.2 [context-decision-filter] In each of the three lens endpoints (`u_and_r_queue`, `emerging_leaders_queue`, `building_bases_queue`), fetch context, compute multiplier, decide suppression via `lens_id in multiplier.suppress_lenses`
- [ ] 5.3 [context-decision-filter] Suppressed responses SHALL still compute the full result list (so frontend can "view anyway"); only the `suppressed` and `suppression_reason` fields change
- [ ] 5.4 [context-decision-filter] On suppression, emit INFO log: `context_decision_filter: lens=<id> suppressed reason="participation=<P> + leadership=<L>"`
- [ ] 5.5 [context-decision-filter] Confirm `building-bases` is never suppressed (defensive assert at start of `_with_context_envelope` for `lens_id == "building-bases"`)

## 6. Backend — Validation

- [ ] 6.1 [context-decision-filter] Curl `GET /api/v1/queue/u-and-r` returns 200 with `suppressed`, `suppression_reason`, `context_snapshot`, `results` keys present
- [ ] 6.2 [context-decision-filter] Curl `GET /api/v1/queue/building-bases` returns `suppressed: false` even when context engine reports COLLAPSING (manual: temporarily force the descriptor or wait for natural condition)
- [ ] 6.3 [context-decision-filter] Curl `GET /api/v1/transitions/actionable` returns the wrapped envelope `{context_snapshot, setups}` and each setup has `context_warnings` (possibly empty)
- [ ] 6.4 [context-decision-filter] Confirm INFO log line appears when a suppression actually fires; tail the backend log during the curl test
- [ ] 6.5 [context-decision-filter] Cold-start test: clear context engine cache, hit any of the four endpoints — verify `context_snapshot` returns `UNKNOWN` and nothing is suppressed

## 7. Frontend — Queue page suppression rendering

- [ ] 7.1 [context-decision-filter] Update the TypeScript types in `frontend/lib/api.ts` (or wherever queue lens types live) to include the four new fields on the queue response
- [ ] 7.2 [context-decision-filter] In `frontend/app/queue/*/page.tsx` (each of the three lens pages), add a state hook `viewAnyway: boolean` defaulting to `false`
- [ ] 7.3 [context-decision-filter] When `response.suppressed && !viewAnyway`, render a `SuppressionCard` component instead of the result list — show headline, `suppression_reason`, `context_snapshot`, and a "view anyway" button that flips local `viewAnyway` state
- [ ] 7.4 [context-decision-filter] When `viewAnyway === true`, render the results normally with a subtle banner at the top reminding the operator that this lens is currently suppressed by context
- [ ] 7.5 [context-decision-filter] Always render the `context_snapshot` at the top of the queue page (small label "Evaluated under: PARTICIPATION × LEADERSHIP") regardless of suppression

## 8. Frontend — Actionable warnings + envelope adoption

- [ ] 8.1 [setup-lifecycle] Update `frontend/components/dashboard/TopActionableSetups.tsx` API response type from `ActionableSetup[]` to `{context_snapshot, setups: ActionableSetup[]}`; adapt the fetch handler to read `data.setups`
- [ ] 8.2 [setup-lifecycle] Add `context_warnings?: string[]` field to the `ActionableSetup` TypeScript interface
- [ ] 8.3 [setup-lifecycle] Pass `contextWarnings={setup.context_warnings}` into `<CompactSetupCard>`
- [ ] 8.4 [setup-lifecycle] In `frontend/components/dashboard/CompactSetupCard.tsx`, accept `contextWarnings?: string[]` prop; render a small amber badge near the priority score when the array includes `"leadership_exhausted"`

## 9. Frontend — MarketContextBar suppression indicator

- [ ] 9.1 [context-decision-filter] Modify `frontend/components/dashboard/MarketContextBar.tsx` to derive `affected_lenses` locally from the current participation + leadership it already has (use a tiny mirror of the rule lookup, or fetch from any queue endpoint and read `suppressed` — pick the lighter option)
- [ ] 9.2 [context-decision-filter] When `affected_lenses.length > 0`, render a small badge on the right of the bar like `· suprime ${affected_lenses.length} lens${plural}`; hovering shows the list
- [ ] 9.3 [context-decision-filter] Visual smoke test: with a known context combination, confirm the bar shows the badge and the queue page shows the suppression card simultaneously

## 10. Frontend — Guide update

- [ ] 10.1 [context-decision-filter] Add new section `id="context-filter"` to `frontend/app/guide/page.tsx` titled "Cómo el contexto filtra los setups"; explain the three multiplier outcomes, the suppression rules per lens, the building-bases exception, and the "view anyway" override
- [ ] 10.2 [context-decision-filter] Add the new section to the table of contents

## 11. Documentation + memory

- [ ] 11.1 [context-decision-filter] Module docstring in `context_decision_filter.py` links to this change directory and to `market-context-engine-phase-1`
- [ ] 11.2 [context-decision-filter] Update MEMORY.md with entry pointing to new `context_decision_wiring_started.md` memory file
- [ ] 11.3 [context-decision-filter] Create memory file `context_decision_wiring_started.md` (project type) noting: Phase 1 ship date, rules summary, building-bases never suppressed, "view anyway" is UI-only, composition with old `_REGIME_CONT_MULT` is intentional, recalibration milestone Aug 2026

## 12. Spec archival

- [ ] 12.1 [context-decision-filter] After 2-3 days of operator validation, run `openspec apply market-context-decision-wiring` to archive
- [ ] 12.2 [context-decision-filter] Confirm the new `context-decision-filter` spec lands under `openspec/specs/` and the `setup-lifecycle` delta is merged into the existing spec

## 13. End-to-end verification

- [ ] 13.1 [context-decision-filter] Manual end-to-end: simulate (or wait for) a hostile combination, confirm bar shows suppression badge, queue page shows suppression card, "view anyway" reveals results, all four endpoints return matching `context_snapshot`
- [ ] 13.2 [context-decision-filter] Performance check: cold-call latency on `/queue/u-and-r` and `/transitions/actionable` stays within 2× of pre-change baseline (one extra context fetch, cached after first call)
- [ ] 13.3 [context-decision-filter] Operator validation (2-3 day soft window): Fernando uses the new suppression cards and warnings in normal workflow, confirms rules feel right and override is reachable
