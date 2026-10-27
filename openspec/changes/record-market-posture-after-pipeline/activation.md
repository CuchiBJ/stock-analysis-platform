# Activation follow-up — 2026-10-27

The user requested completion after implementation and verification and explicitly selected **production** as the activation target. Production activation is complete; see `deployment.md`.

## Confirmed local state

- API is running from this checkout and `http://127.0.0.1:8000/health` returns healthy. This endpoint alone does not validate database schema or scheduler activity.
- `.run/scheduler.pid` contains 7618, but that process no longer exists. The scheduler is not running under the saved PID.
- Runtime configuration identifies a development database at localhost:5432, database stock_analysis. Credentials were not printed or copied.
- The existing Docker container `stock-analysis-db` was stopped. Started that same container temporarily with its existing persistent volume to inspect schema, then returned it to its original stopped state after the user selected production. No database was restored, reset or recreated.
- Read-only schema checks report Alembic revision `b7c8d9e0f1a2` and no `market_posture_records` table.
- There are 64 existing journal trades. The pending identity migration adds nullable ownership, and its next contract migration rejects unclaimed trades. Assigning their ownership requires a user-specific decision; no owner was fabricated.
- The chain to head also includes an unrelated legacy outcome reset. It was inspected and not executed.

## Resolution

The user selected production. Its schema is already at `f6a7b8c9d0e1` and includes the posture table. Its four existing affected source files exactly matched the implementation baseline. No local migration chain, journal ownership assignment, guard bypass or out-of-order table creation was needed or performed.

The scoped production release rebuilt and recreated only API and scheduler; active hashes, startup, health, protected routes and preservation of other service containers were verified. At activation it was before the eligible post-close window, so a new automatic posture observation is expected only after that processing completes, not immediately at deployment. No migration or historical backfill was performed.
