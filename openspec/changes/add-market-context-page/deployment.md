# Production deployment — 2026-10-21

User explicitly requested deployment after approving the visual and implementation.
Target: https://129-159-125-184.sslip.io/market-context .

## Scope and activation

Transferred the nine runtime files from this change, then added `frontend/middleware.ts` to include the new page in the existing initial login redirect. Before replacement, remote existing files and dependency manifests matched local HEAD SHA-256 values. No unrelated working-tree files, secrets, tests or database content were transferred.

Built API and frontend with production Compose on the VM. Activated only those services using `up -d --no-deps --no-build --wait`. PostgreSQL, Redis, scheduler and Caddy were not replaced. No migrations, credential changes, backfills or database writes were performed.

Runtime files: endpoint, breadth/overview/volatility services; navigation layout, page entry, MarketContextPage, ContextEvidence, presentation types/helpers, and middleware. See verification.md for their paths.

Initial nine-file archive SHA-256:
`7f225827a55364f25ad50600f394c17de1b8e0295bd16d7931393f95896da92d`.
Final middleware SHA-256:
`f1964fa7f2d25498d45b6aa6bf2b9d9099017cfb2bb4c21af5a312c6523aa61d`.

Final active images:
- API: `sha256:d6b7d2e9d373f8f043f10dbd36cc24564521c1a1960866067790d7dffe6a5aa9`
- Frontend: `sha256:7b9ce554226fc09fd7d4920af2b89b40a3e6803ca66937119465592771eebe5c`

## Verification

- API and frontend healthy; PostgreSQL/Redis healthy; scheduler/Caddy running.
- Public `/health` and `/login`: HTTP 200.
- Anonymous `/market-context` and `/dashboard`: HTTP 307 to login.
- Anonymous new overview and volatility endpoints: HTTP 401. Existing current endpoint also returned 401 at initial activation.
- Compiled page exists in active frontend image; active backend source SHA-256 values match the local release manifest.
- Dashboard MarketContextBar and MarketContextDrawer hashes unchanged from pre-deployment baseline.
- Candidate API image passed a network-disabled synthetic VIX/parser/code-compilation check on Python 3.11.16.
- Browser integration was rerun locally after adding middleware: initial unauthenticated redirect, synthetic authenticated view, retries, sector details and session loss passed. Frontend unit tests (22), lint and typecheck also passed again.
- Production frontend build passed. Existing Next Edge-runtime compatibility warnings were emitted during build.
- OpenSpec validation and final diff whitespace checks passed.

Operational read-only data check used `SET TRANSACTION READ ONLY` and a 30-second statement timeout. It resolved context 2026-10-21: 15 new highs, 7 new lows, 407 eligible, 47 excluded, 8 sector groups; both constituent totals reconciled. SPY had a 2026-10-21 observation. Cboe returned VIX 17.31 for 2026-10-20, explicitly dated as older than context.

The first standalone operational script omitted the User model registration and failed before its data read; rerunning with the same model registration used by the app succeeded. This did not affect the running API or require an application change.

## Residual data limitation

QQQ's newest stored observation is 2026-08-17; its trend is unavailable. The page explicitly displays that date and the missing indicators. No production backfill was performed: refreshing QQQ ingestion is separate work. An authenticated production browser inspection was not performed; authenticated interaction checks used synthetic local fixtures, and production checks used protected HTTP rejection plus internal read-only operational verification.

## Rollback assets

Directory: `/opt/stock-analysis/releases/market-context-page-20261021/`.
- `source-before.tgz`: pre-change endpoint, breadth service and navigation layout.
- `middleware.before.ts`: pre-change middleware.
- `market-context-page-20261021.tgz`, manifest JSON and `middleware.after.ts`: deployed sources.
- `build.log`, `frontend-route-build.log`: build records.
- Image `stock-analysis-api:before-market-context-page-20261021`.
- Image `stock-analysis-frontend:before-market-context-page-20261021`.

If rollback is requested, restore the archived existing files and middleware, remove the six newly added runtime files, retag the saved images as the respective latest images, and recreate only API/frontend with `--no-deps --no-build --wait`. No database rollback is needed. Preserve any newer changes before applying these steps.
