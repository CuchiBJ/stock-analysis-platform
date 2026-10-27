# Production deployment — 2026-10-26

Target: https://129-159-125-184.sslip.io/market-context. User explicitly requested deployment after implementation and verification.

## Scope

Nine runtime files only: the eight components under `frontend/components/market-context/` and `frontend/lib/market-context-labels.ts`. Production source SHA-256 values for all eight existing files exactly matched the pre-change baseline; the labels helper did not previously exist. No full checkout synchronization, backend release, database migration, scheduler restart or configuration change.

## Recovery assets

Directory: `/opt/stock-analysis/backups/market-context-reading-20261026T192610Z`.

- `source-before.tar.gz` and `existing-files.txt`: the eight previous component sources.
- `source-before.sha256`, `source-after.sha256`, `release-files.txt`, `source-after.tar.gz`: verified release manifest and source bundle.
- `image-before.txt` and `rollback-tag.txt`: previous running image ID and retained rollback tag.
- `build.log`, `activation.txt`, `unchanged-containers-before.txt`, `unchanged-containers-after.txt`: build/activation evidence.

## Rollout and checks

- Production Docker build completed successfully, including TypeScript and static page generation, while the old frontend kept serving traffic.
- Recreated only frontend using Compose `up -d --no-deps --no-build --wait --wait-timeout 180 frontend`; container became healthy.
- Active frontend image: `sha256:7cb2d06ac22180e4ccf6e19855e10da545c104ac8b2084169d1937e5cfa84de3`.
- API, scheduler, PostgreSQL, Redis and Caddy container IDs matched exactly before and after activation.
- Verified release markers in the actual running container's compiled JavaScript, decoding minifier Unicode/hex escapes: five-section reading structure, historical session inspection label and daily-extremes label.
- Public HTTPS smoke: `/health` 200, `/login` 200, `/` 307, `/market-context` 307 to login with return destination, unauthenticated `/api/v1/market-context/overview` 401.
- Authenticated interaction and desktop/tablet layout were verified locally with synthetic fixtures before deployment. No authenticated production browser session was used for this smoke check.

Two initial smoke assertions needed correction: minified non-ASCII label matching required decoding escapes, and the protected root correctly returns 307 rather than 200. Neither required application or configuration changes.

## Rollback

From `/opt/stock-analysis`, restore the eight original component sources from `source-before.tar.gz`, remove only the newly added `frontend/lib/market-context-labels.ts`, retag the saved image ID in `image-before.txt` to `stock-analysis-frontend:latest`, and recreate only frontend with the same `--no-deps --no-build --wait` command. Recheck container health and protected HTTPS routes. No database action is needed.
