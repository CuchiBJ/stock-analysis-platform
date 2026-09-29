## 1. Specification and baseline reconciliation

- [x] 1.1 [priority-engine] Reconcile/archive the completed `refine-actionable-ranking` change before implementation so its reusable RS helper is retained while its actionable-surface requirements can be retired cleanly.
- [x] 1.2 [forming-setups] Capture focused regression fixtures for a BE-like formation, a DOCN-like formation, a near-high breakout, a damaged laggard, and an empty-result regime without depending on live production data.
- [x] 1.3 [forming-setups] Inventory every `/transitions/actionable`, `get_actionable_setups`, `TopActionableSetups`, actionable diagnostic, chat-tool, guide, and test consumer and record its migration target.

## 2. Shared transition boundary

- [x] 2.1 [forming-setups] Extract the current Setup Feed candidate/selection logic from the oversized transitions endpoint into a reusable service without changing response semantics.
- [x] 2.2 [forming-setups] Add parity tests proving the extracted selector returns the same symbols, ordering, transition fields, limit behavior, and empty/error behavior as the pre-change Setup Feed.
- [x] 2.3 [forming-setups] Expose a lightweight current-feed symbol set from the shared selector for formation-stage exclusion without inferring current state from historical observations alone.

## 3. Formation eligibility and ranking

- [x] 3.1 [forming-setups] Create `forming_setup_service.py` with latest-snapshot loading, canonical quality/market-cap/structure gates, lifecycle-state evaluation, and invalidation-first rejection.
- [x] 3.2 [forming-setups] Implement pure formation eligibility that has no hard 52-week-high or EMA-trigger-membership gate and returns structured rejection reasons.
- [x] 3.3 [priority-engine] Implement the 0–100 formation score with 35/25/20/10/10 component weights, neutral missing-history behavior, deterministic tiebreakers, and no structural-age contribution.
- [x] 3.4 [priority-engine] Calibrate component bucket boundaries against representative historical fixtures/distributions, record the evidence in tests, and keep the specified weights and eligibility unchanged.
- [x] 3.5 [forming-setups] Implement current-feed exclusion, minimum score 55, maximum six results, honest empty output, context snapshot, formation narrative, primary risk, and full score breakdown.
- [x] 3.6 [forming-setups] Add service tests for invalidation precedence, far-from-high eligibility, weak-RS risk without hard rejection, structural-age neutrality, missing history, feed promotion/exclusion, sorting, cutoff, and empty results.

## 4. API and diagnostics

- [x] 4.1 [forming-setups] Add the protected `GET /api/v1/transitions/forming` route with validated `limit <= 6` and a typed response contract.
- [x] 4.2 [symbol-diagnostic] Replace actionable diagnosis with shared formation eligibility, status, rank, cutoff gap, component breakdown, and `promoted_to_feed` explanation.
- [x] 4.3 [symbol-diagnostic] Preserve live/queue diagnostic behavior and add parity tests proving diagnostics agree with both Setups Forming and the Setup Feed on the same snapshot.
- [x] 4.4 [forming-setups] Migrate the chat tool from actionable ranking to the formation-stage service and update its schema/copy to preparation language.

## 5. Dashboard workflow and presentation

- [x] 5.1 [forming-setups] Build a `SetupsForming` dashboard component with authenticated fetching, metrics-event refresh, and complete loading, empty, error, and session-expired behavior.
- [x] 5.2 [setup-card-presentation] Adapt or replace the compact card so it shows preparation narrative, next-trigger distance, structure/contraction evidence, RS direction, and primary risk in at most 15 visible elements.
- [x] 5.3 [setup-card-presentation] Remove continuation probability, actionable/confidence language, hardcoded transition chrome, and structural-age freshness badges from the formation card.
- [x] 5.4 [forming-setups] Reorder the dashboard to place Setups Forming before Setup Feed, update keyboard anchors, preserve sector context, and confirm the two panels never display the same symbol for one snapshot.
- [x] 5.5 [forming-setups] Add frontend tests for rendering, six-card scarcity, progressive disclosure/navigation, non-duplication, and all loading/empty/error states.

## 6. Retirement and documentation

- [x] 6.1 [priority-engine] Remove `/transitions/actionable`, actionable-only endpoint scoring/wrappers, dead frontend code, and obsolete tests after every in-repository consumer has migrated.
- [x] 6.2 [symbol-diagnostic] Remove stale actionable labels and criteria mappings from the symbol page while preserving historical transition evidence.
- [x] 6.3 [forming-setups] Update the operator guide to describe the linear workflow, exact formation eligibility/ranking, structural maturity versus signal freshness, promotion to Setup Feed, scarcity, and diagnostic states.
- [x] 6.4 [forming-setups] Review API/docs/search results to ensure no live product copy still presents Setups Forming as actionable, predictive, or a buy list.

## 7. Verification

- [x] 7.1 [forming-setups] Run the focused backend service, endpoint, transition parity, diagnostic, and historical fixture tests.
- [x] 7.2 [setup-card-presentation] Run focused frontend component tests plus `npm run lint` and `npm run typecheck`; run `npm run build` because dashboard/API contracts change.
- [x] 7.3 [priority-engine] Run the broader backend suite and relevant Ruff/mypy checks, reporting any pre-existing or environment-blocked failures separately. (`pytest tests`: 448 passed; Ruff and mypy are not installed in the backend venv.)
- [x] 7.4 [forming-setups] Perform an authenticated browser smoke check of market context → Setups Forming → Setup Feed → symbol diagnostic, including an empty panel and a promoted symbol.
- [x] 7.5 [forming-setups] Review the final diff for unrelated changes, verify OpenSpec artifacts, confirm no schema migration or new dependency was introduced unexpectedly, and document rollback/deployment ordering.

## 8. Full formation catalog

- [x] 8.1 [forming-setups] Add a protected catalog route that returns every candidate passing the existing formation criteria in canonical rank order while preserving the six-result dashboard contract.
- [x] 8.2 [forming-setups] Add a `Ver más` affordance to the dashboard panel and a dedicated authenticated page that renders the full ranked candidate list with the established formation cards and complete loading, empty, error, and retry states.
- [x] 8.3 [forming-setups] Add focused backend and frontend contract tests for the full catalog and dashboard-to-detail navigation.
- [x] 8.4 [forming-setups] Run focused tests plus frontend lint, typecheck, and production build; review the final diff for unrelated changes.
