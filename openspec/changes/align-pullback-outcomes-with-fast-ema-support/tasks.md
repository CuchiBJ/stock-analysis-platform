## 1. Pullback outcome rule

- [x] 1.1 [entering-pullback-outcomes] Add a pure chronological support/continuation classifier and regression coverage for recovered wicks, invalidation, ordering, missing inputs, and the ten-session boundary.
- [x] 1.2 [entering-pullback-outcomes] Integrate completed-session evaluation and bound historical price queries without changing other transition rules.

## 2. Historical synchronization and explanation

- [x] 2.1 [entering-pullback-outcomes] Add a data-only migration clearing terminal legacy pullback outcomes while preserving all detection snapshots and unrelated transitions.
- [x] 2.2 [entering-pullback-outcomes] Recompute pullbacks from ordered stored prices in manual reclassification and test stale-field reset and other-family preservation.
- [x] 2.3 [entering-pullback-outcomes] Explain the pullback rule in Calibration.

## 3. Verification

- [x] 3.1 [entering-pullback-outcomes] Run focused backend regressions, inspect Alembic heads and exercise the data migration against a disposable database, run frontend tests/type checks, validate OpenSpec, and independently review the final diff. Record results and deployment limitations.

## 4. Authorized production rollout

- [x] 4.1 [entering-pullback-outcomes] After the operator's explicit production request, deploy only the five production files, back up observations and the migration revision, pause evaluator writes, apply the data migration, reevaluate only entering pullbacks, verify preserved detection context and unrelated transitions, restart services, and verify Calibration and public health.

## Verification results

- Backend: `venv/bin/python -m pytest -q --disable-warnings` for `test_pullback_outcome.py`, `test_pullback_outcome_migration.py`, `test_outcome_classification.py`, `test_calibration_endpoint.py`, `test_follow_through.py`, `test_empirical_probability_calculator.py`, and `test_batch_transition_scanner.py`: **117 passed**. Run from an isolated temporary working directory with dummy database/provider settings; no repository `.env` or services were read or used.
- Migration upgrade and downgrade executed against disposable in-memory SQLite fixtures, preserving detection fields, pending rows, and unrelated transitions. Alembic script graph has one head, `e5f6a7b8c9d0`, across 26 revisions. The subsequently authorized PostgreSQL production migration also completed successfully.
- Frontend: `npm test`: **17 passed**; `npm run typecheck` and `./node_modules/.bin/eslint app/calibration/page.tsx`: passed.
- `openspec validate align-pullback-outcomes-with-fast-ema-support --strict` and `git diff --check`: passed.
- Independent read-only review found an invalid-close arithmetic gap; fixed it and added partial-window and twentieth-close regressions. Reviewer reran the 53 pullback tests successfully and found no further actionable issue.
- Backend Ruff was unavailable (`No module named ruff`); no dependency was installed. Existing runtime also requires postponed annotations for Python compatibility, which the new pure module supplies.
- Production rollout completed on 2026-10-08 following the operator's explicit request. All 3,784 entering pullbacks were reevaluated: 583 `SUCCESS`, 2,548 `FAILURE`, 211 `NEUTRAL`, and 442 `PENDING`. The backup comparison confirmed unchanged detection context and all 28,444 unrelated observations. API, scheduler, and frontend run the new images; public health and protected Calibration access passed. Recent delivery rate is 27.54% (38/138 settled); historical delivery rate is 17.44% (583/3,342 settled). See `production-rollout.md` for evidence and rollback assets. Detection-seeded EMA and missing-session limitations remain as documented in `design.md`.
