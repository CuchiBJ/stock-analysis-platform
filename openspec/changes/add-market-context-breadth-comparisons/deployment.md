# Production deployment

## SPY calendar correction — 2026-10-21

Replaced only `backend/app/services/market_context_breadth.py`, rebuilt the API,
and activated it with `--no-deps --no-build --wait`. API health and public HTTPS
health passed. No migrations or data modifications were performed.

The global date selection had admitted an isolated 2026-09-07 record absent
from every qualified symbol and SPY. The corrected service uses only SPY dates.
Local verification: 88 backend tests passed, including orphan-date and
missing-SPY regressions; strict OpenSpec validation and diff checks passed.

Read-only operational verification of the deployed service for 2026-10-20:
421 eligible / 49 excluded for annual extremes, 9 new highs / 21 new lows (30%).
From-open coverage is 470; daily ±4% coverage is 469. No authenticated browser
visual check was performed.

Service SHA-256: `1bd943a13a902c8aa426a43ed4cf076f744f512bace3e0ba45ec43d918d3902f`.
Rollback assets: image `stock-analysis-api:before-spy-calendar-20261021` and
`/opt/stock-analysis/releases/breadth-spy-20261021/market_context_breadth.before.py`.

Deployed to `129-159-125-184.sslip.io`; health rechecked on 2026-10-21.

## Scope

Transferred only the five runtime files for breadth: the new breadth service,
Market Context engine and endpoint, and MarketContextBar/MarketContextDrawer.
The four existing remote files matched the local HEAD baseline before replacement.
Unrelated local pullback and calibration changes were not transferred.

Built `api` and `frontend` on the VM and activated them with Compose
`up -d --no-deps --no-build --wait --wait-timeout 120 api frontend`.
No migrations, database operations, or scheduler replacement were performed.

Release archive SHA-256:
`dbc832f7720d6d011a068a5dd59bea480bee6724793a227981f14fcf0727af4d`.

## Verification

- API and frontend report healthy; PostgreSQL/Redis healthy; scheduler/Caddy running.
- Public HTTPS `/health`: healthy; `/login`: HTTP 200.
- Unauthenticated Market Context endpoint: HTTP 401 at activation.
- All three changed backend files in the active API container match local SHA-256 hashes.
- Active frontend static bundle contains `new_52w_highs_vs_lows`.
- Authenticated visual verification was not performed.

## Rollback assets

Saved on the VM before replacing files:

- `/opt/stock-analysis/releases/breadth-20261020/source-before.tgz`
- `stock-analysis-api:before-breadth-20261020`
- `stock-analysis-frontend:before-breadth-20261020`

For a separately authorized rollback, restore the four source files from the
archive and remove the newly added `backend/app/services/market_context_breadth.py`;
retag the saved images as their respective `latest` tags and recreate only API
and frontend with `--no-deps --no-build`. No database rollback is needed.
