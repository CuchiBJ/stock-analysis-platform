## 1. Contract and backend

- [x] 1.1 [market-context-breadth] Implement isolated batched OHLC breadth calculation and coverage result using SPY's session calendar for resolved `as_of`.
- [x] 1.2 [market-context-breadth] Add breadth values to MarketContext caching and the current endpoint response without changing decision inputs.
- [x] 1.3 [market-context-breadth] Add real database-backed tests for threshold, SPY session history, missing-calendar behavior, eligibility, filtering, and historical date behavior.

## 2. Frontend

- [x] 2.1 [market-context-presentation] Extend API types and render the three accessible breadth rows, counts, ratios, date, and coverage with legacy payload support.
- [x] 2.2 [market-context-presentation] Clarify the existing highs/lows ratio help text and update the drawer presentation tests.

## 3. Verification

- [x] 3.1 [market-context-breadth] Run focused backend and frontend tests and type/lint/build checks; inspect the final diff and synchronize this checklist.
- [x] 3.2 [market-context-breadth] Add and run regression tests for SPY session anchoring, rogue dates, and absent SPY history.
