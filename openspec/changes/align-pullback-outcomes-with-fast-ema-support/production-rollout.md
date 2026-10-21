# Production rollout — 2026-10-08

The operator explicitly requested: “Ejecuta los cambios en producción”. Rollout and final checks completed at 2026-10-08T18:26:16Z on the existing production deployment. Calibration's data cutoff was 2026-10-08.

## Deployed scope

Only these production files were transferred:

- `backend/app/services/pullback_outcome.py`
- `backend/app/services/outcome_tracker.py`
- `backend/app/api/v1/endpoints/calibration.py`
- `backend/alembic/versions/e5f6a7b8c9d0_reset_entering_pullback_outcomes.py`
- `frontend/app/calibration/page.tsx`

Existing production versions of the three modified files matched their local HEAD baselines before transfer. API and scheduler images were built from their existing runtime images with only the scoped files replaced. Frontend was rebuilt from the production checkout with the changed Calibration page. Unrelated local working-tree changes were excluded.

| Service | Verified image ID |
| --- | --- |
| API / migration | `sha256:22a5ab3fe7d38157724b9a81709c1c158b4ab39b0341bca28df7243cb0de1e56` |
| Scheduler | `sha256:ad6a682241380e4ff08cf9e77012500451f5b5bd2f731cb1e09ac746d7ed28de` |
| Frontend | `sha256:271ac8e463e575fcc31baad6e6262eba124da26e315eb6c8cd754584e11c457b` |

## Migration and reevaluation

API and scheduler were stopped during the data operation. A custom PostgreSQL backup of `transition_observations` and `alembic_version` was created before applying revision `e5f6a7b8c9d0` from `d9e0f1a2b3c4`.

A one-off evaluator explicitly selected only `entering_pullback` observations and used the shared reevaluation helper. It processed 3,784 observations in 6.79 seconds and committed the results together.

| Outcome | Before | After |
| --- | ---: | ---: |
| SUCCESS | 1,409 | 583 |
| FAILURE | 1,319 | 2,548 |
| NEUTRAL | 657 | 211 |
| PENDING | 399 | 442 |
| Total | 3,784 | 3,784 |

An initial context checksum included the automatically updated `updated_at` field and therefore differed. A complete comparison against the backup in a session-local temporary table confirmed zero detection-context changes after excluding only outcome fields and `updated_at`. Automatic timestamps changed on 3,747 pullbacks. All fields of the 28,444 other transition observations were unchanged. No public table was restored or replaced for this comparison. Services restarted after the integrity check passed.

## Verification

- API and frontend health checks passed; scheduler was running. All three new containers had zero restarts at verification.
- API and scheduler runtime source hashes matched the local scoped files.
- Frontend server and browser assets contained the new explanation, including recovered wicks and EMA50 invalidation.
- Public HTTPS `/health` returned `{"status":"healthy"}`.
- Unauthenticated `/api/v1/calibration/by-transition-type` returned HTTP 401.
- A read-only invocation of the production Calibration endpoint returned the following recomputed cohorts. Its existing recent window is 21 calendar days; the pullback outcome deadline is ten completed sessions.

| Cohort | Success | Failure | Neutral | Pending | Delivery rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical | 583 | 2,548 | 211 | 442 | 17.44% |
| Recent | 38 | 85 | 15 | 442 | 27.54% |

Delivery rate includes neutral outcomes in the settled denominator; pending observations are excluded. Existing Calibration also exposes decisive success rate: 18.62% historical and 30.89% recent. These are empirical signal outcomes, not realized execution returns. The EMA-seed and stored-session limitations in `design.md` still apply.

## Recovery assets

Production backup directory: `/srv/stock-platform/backups/pullback-20261008-JXdXE0`.

- `observations-before.dump`: private custom-format data backup; catalog readability and SHA-256 verification passed.
- `source-before.tar.gz`: original versions of the three modified source files.
- Old runtime images retained as `stock-analysis-{api,scheduler,frontend,migrate}:rollback-pullback-JXdXE0`.
- Integrity report, reevaluation report, and verified Calibration response are retained with the release artifacts.

A code rollback must also reconcile pullback labels using the saved backup or the documented reset-and-reevaluation approach; retaining new-rule outcomes under old code would misstate the old contract. No rollback was required.
