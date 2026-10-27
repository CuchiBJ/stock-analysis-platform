# Production deployment — 2026-10-27

The user explicitly selected production after asking to complete the task.

Target: https://129-159-125-184.sslip.io/market-context, SSH ubuntu@129.159.125.184, checkout `/opt/stock-analysis`.

## Scope and preflight

Only six runtime files were transferred: scheduler, current-context engine, posture-record serializer service, market-context endpoint, new post-close coordinator and new posture-capture service. All four previously existing sources exactly matched the SHA-256 baseline saved before implementation. Both new module paths were absent before release. No complete-checkout synchronization, frontend release, configuration change, migration or historical backfill was performed.

Read-only production checks confirmed Alembic `f6a7b8c9d0e1`, the existing `market_posture_records` table, latest metrics dated 2026-10-26, and the actual 2026-10-26 posture record. The existing record was not reconstructed or relabeled.

## Recovery assets

Directory: `/opt/stock-analysis/backups/posture-pipeline-20261027T131327Z`.

- `source-before.tar.gz`, `existing-files.txt`, `source-before.sha256`: four original sources and verified hashes.
- `source-after.tar.gz`, `release-files.txt`, `source-after.sha256`: exact six-file release and hashes.
- `images-before.txt`: previous API and scheduler image IDs.
- Rollback image tags: `stock-analysis-api:rollback-posture-pipeline-20261027T131327Z` and `stock-analysis-scheduler:rollback-posture-pipeline-20261027T131327Z`.
- `build.log`, `activation.log`, `services-after.txt`: build and activation evidence.
- `unchanged-before.txt`, `unchanged-after.txt`, `unchanged-verified.txt`: identical frontend/PostgreSQL/Redis/Caddy container identities.

No database backup/restore was needed because no migration or manual data modification was part of this release. Scheduler resumes its existing ordinary processing.

## Activation and verification

- Built only API and scheduler images while prior services remained live.
- A disposable container using Python 3.11, dummy configuration and `--network none` verified all six source hashes, model mapper registration, coordinator wiring and the compatible uncached analyze option. An initial check could not read the read-only hash manifest under the app UID; making only that non-secret manifest readable resolved it before any activation.
- Recreated only API/scheduler with Compose `up -d --no-deps --no-build --wait --wait-timeout 180 api scheduler`.
- Activation: **2026-10-27 13:15:05 UTC / 10:15:05 Argentina**.
- API: healthy; scheduler: running; both reported 0 restarts during post-deploy verification.
- Active API image: `sha256:016e9df41d8ab0afa3bb9d8e367b08e3438fe0b3a5d308a15b32ed063e3973a4`.
- Active scheduler image: `sha256:ff99455f68500eaf5662fbd28c3b9a4182792ef0009a18fdd7d802a4ca848741`.
- Checked all six source hashes inside both actual running containers; they match the release.
- Scheduler logs confirm loop startup, tier assignments loaded from the database and startup price processing begun. No forced post-close calculation was performed before the market session.
- HTTPS checks: `/health` 200, `/login` 200, `/market-context` 307 to authentication; unauthenticated current/overview both 401.
- Frontend, PostgreSQL, Redis and Caddy container IDs remained identical before/after activation.

## First automatic observation

The eligible 2026-10-27 post-close window begins at **16:10 America/New_York / 17:10 America/Argentina/Buenos_Aires / 20:10 UTC**. Capture is awaited after prices and sufficiently covered same-session metrics are processed; it is not guaranteed at the window's opening instant. A failed attempt reports the reason in `post_close_cycle` and retries after at least 300 seconds from completion.

At activation it was before that window. Automatic capture for today's session has therefore not yet occurred or been claimed as verified. With the existing 2026-10-26 record, comparison can become available once the actual 2026-10-27 record and matching SPY reference dates exist. The missing 2026-10-23 observation stays missing.

## Rollback

Restore the four sources from `source-before.tar.gz`, remove only the two new modules listed in `release-files.txt`, retag the retained prior images to the API/scheduler current tags, and recreate only those two services with the same no-dependency activation command. Verify service health and protected HTTPS routes again. Keep all existing posture records; no database downgrade or restore is part of code rollback.
