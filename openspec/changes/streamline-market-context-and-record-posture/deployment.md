# Production deployment — 2026-10-26

Target: https://129-159-125-184.sslip.io/market-context, SSH ubuntu@129.159.125.184, checkout /opt/stock-analysis.

## Scope
User explicitly requested production deployment after implementation of points2,3,4. Release contains the compact posture header, compact sector evolution, and observed posture records.18 scoped files were transferred; the prior source hashes exactly matched the implementation baseline.

The separate QQQ ingestion correction was intentionally excluded: deploying it before historical recovery can calculate apparently current indicators over a discontinuous series. No QQQ backfill or activation was performed in this release.

## Recovery assets
- Directory: /opt/stock-analysis/backups/compact-posture-20261026T135824Z
- Existing sources: source-before.tar.gz, existing-files.txt and release manifest/hashes.
- PostgreSQL: stock_analysis_20261026T135824Z.dump, verified nonempty with pg_restore --list; SHA256 retained in database-backup.sha256.
- Running image IDs: images-before.txt; tagged stock-analysis-api:rollback-compact-20261026 and stock-analysis-frontend:rollback-compact-20261026.
- Build output: build.log. Existing services remained live during compilation.

## Migration and rollout
- Built api, frontend and migrate images successfully (including production TypeScript build).
- Applied `alembic upgrade f6a7b8c9d0e1`; production advanced from e5f6a7b8c9d0 to f6a7b8c9d0e1 (head).
- Recreated API and frontend with Compose `--no-deps --wait`; both became healthy. Scheduler, PostgreSQL, Redis and Caddy remained running.
- HTTPS health returned200; unauthenticated market-context redirected307 to authentication, and current/overview returned401 without credentials.
- Authenticated browser confirmed compact header, twelve-sector table, and opening/closing the Energy history with actual dated rates and coverage.
- Production PostgreSQL read-only check found one real posture record: session2026-10-26, FUERA, recorded_at2026-10-26T14:02:54.598217+00:00. No earlier posture was invented; UI explicitly reports absent prior-session evidence.
- Screenshot: /tmp/market-context-production-20261026.jpg.
- No QQQ recovery or QQQ refresh activation was included.

## Rollback boundary
The new posture table is additive and compatible with the prior API. If code rollback is needed, restore recorded API/frontend images and sources; retain the new table rather than deleting captured history. Database restore is a separate exceptional operation, not an automatic code rollback step.

## Subsequent QQQ recovery
After separate explicit authorization, QQQ history recovery and automatic refresh activation were completed later on2026-10-26. See ../fix-market-context-benchmark-refresh/deployment.md; the exclusions above describe this earlier UI release.
