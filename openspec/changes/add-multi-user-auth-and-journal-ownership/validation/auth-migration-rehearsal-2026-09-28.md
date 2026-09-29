# Authentication migration rehearsal — 2026-09-28

## Scope and isolation

- Source: latest production backup available at rehearsal time.
- Backup size: 259,492,328 bytes.
- Backup SHA-256: `d1db61c02fcde2a4e436725fdb5e88a0ebae70a11dba8c26c1654761a1b86676`.
- Execution environment: isolated Docker network, disposable PostgreSQL containers, no published ports.
- Production database and running production services were not modified or restarted.
- This report contains aggregate counts and one-way checksums only. It contains no journal rows, symbols, user identifiers, tokens, or credentials.

## Baseline restore

The backup restored successfully at Alembic revision `b7c8d9e0f1a2`.

| Invariant | Baseline |
| --- | ---: |
| Journal trades | 65 |
| Open trades | 4 |
| Closed trades | 61 |
| Decision-parent links | 11 |
| Linked observations | 21 |
| Stop events | 29 |
| Invalid parent links | 0 |
| Invalid linked observations | 0 |
| Orphan stop events | 9 |

The expansion migration correctly aborted when it found the nine orphan stop events. A dedicated preflight was added rather than weakening the migration or silently deleting data.

## Integrity preflight

The cleanup tool was run first in dry-run mode and then with `--execute`.

| Mode | Orphans before | Rows selected | Orphans after in transaction | Persisted stop events | Persisted orphans |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dry-run | 9 | 9 | 0 | 29 | 9 |
| Execute | 9 | 9 | 0 | 20 | 0 |

Only stop events without an existing parent trade were removed. All 65 trades and all 20 valid stop events remained.

## Expand, bootstrap, claim, and contract

1. Expansion advanced from `b7c8d9e0f1a2` to `c8d9e0f1a2b3`; `owner_user_id` was nullable.
2. A synthetic, verified administrator was created with the standalone bootstrap CLI.
3. Claim dry-run selected all 65 unowned trades and rolled back.
4. Claim execution assigned all 65 trades to the administrator.
5. A second claim execution assigned 0 trades, proving idempotence.
6. Contract advanced to `d9e0f1a2b3c4`; `owner_user_id` became non-null, no null owners remained, and the owner foreign key was present.

Protected invariants were identical before and after ownership assignment:

| Invariant | Before | After |
| --- | ---: | ---: |
| Trades | 65 | 65 |
| Open / closed | 4 / 61 | 4 / 61 |
| Decision-parent links | 11 | 11 |
| Linked observations | 21 | 21 |
| Valid stop events | 20 | 20 |
| Invalid relationship targets | 0 | 0 |
| Quantity sum | 1157.6566 | 1157.6566 |
| Entry notional sum | 36762.14636 | 36762.14636 |
| Realized P&L sum | -449.0699999999999532 | -449.0699999999999532 |

One-way checksums also matched before and after the claim:

- Trade IDs: `d8af1fca9391a4350095907fb119c05d59470b6ce34153762ed94bedbef179df`
- Trade fields excluding ownership/update timestamp: `984d073cbe9aa116475b9ad2171798152447bdf4bf053ae3cfde4d6123abd838`
- Valid stop events: `537112edbfb2b25c73748a0d02eda833218c22ff4c470a732ff0ad966af0de1e`

## Full restore proof

The unchanged source backup was restored again into a second empty PostgreSQL volume after the completed migration rehearsal. The independent restore returned revision `b7c8d9e0f1a2`, 65 trades, and 29 original stop events. This proves the source backup remained usable and unmodified.

## Application verification

- Backend official suite: 456 tests passed.
- Focused administrator-only authentication matrix: 22 tests passed.
- Frontend unit tests: 15 passed.
- Frontend lint, typecheck, and production build passed.
- Administrator-only production smoke passed: login rendered normally while registration and recovery redirected to login.
- HTTPS Chromium smoke passed for protected redirect, registration, email verification, login, profile read/update, logout, recovery/reset, post-reset login, and expired-session rejection.
- Shared-browser Chromium smoke passed: the second user observed no first-user profile, journal rows, statistics, drafts, or account balance.
- The adversarial API matrix passed for independent list, stats, export, import/replace, create, edit, close, delete, stop history, queue-to-trade, backfill, and broker-ID behavior; foreign identifiers returned indistinguishable not-found responses without mutation.

## Production execution

- A fresh pre-migration backup was created at `stock_analysis_20260928T184048Z.dump` (261,743,753 bytes; SHA-256 `96aca9c96deef0eb30da304afb2d18a7345b288130088246551f93afdea517a8`).
- The integrity preflight removed the same 9 orphan stop events identified by rehearsal and retained 20 valid stop events.
- Expansion advanced production from `b7c8d9e0f1a2` to `c8d9e0f1a2b3`; a verified active administrator was bootstrapped without exposing its password.
- Claim dry-run and execution both preserved all aggregate values and checksums while assigning all 65 trades. A second dry-run selected 0 trades, proving production idempotence.
- Contract advanced production to `d9e0f1a2b3c4 (head)`. API, frontend, scheduler, PostgreSQL, and Redis returned healthy.
- Production runs in administrator-only mode. The canonical HTTPS origin is accepted for credentialed requests; registration and recovery remain disabled.
- Authenticated browser verification loaded the administrator dashboard and historical journal. The duplicate legacy WebSocket hook discovered during this verification was removed in hotfix `61ed4bd`; the rebuilt production bundle contains no legacy reconnect-loop module and a fresh browser load reports no console errors.

## Result

The migration is operationally rehearsed and complete in production. Its data invariants pass, all legacy trades belong to the verified administrator, and the deployed application is healthy. SMTP remains unnecessary while public account flows are disabled; administrative recovery uses the server-side password reset.
