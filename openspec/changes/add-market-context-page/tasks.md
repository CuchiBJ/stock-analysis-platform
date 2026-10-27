## 1. Backend evidence

- [x] 1.1 [market-context-page] Add optional breadth constituents and a protected overview with dated SPY/QQQ evidence, preserving existing current endpoint behavior.
- [x] 1.2 [market-context-page] Add bounded, cached Cboe daily VIX retrieval and isolated protected volatility endpoint.

## 2. Dedicated frontend

- [x] 2.1 [market-context-page] Add navigation and approved page with all existing context evidence, benchmark hierarchy, sector disclosure, and independent VIX/error/session states.

## 3. Verification

- [x] 3.1 [market-context-page] Test dates, missing data, breadth reconciliation, provider failure/cache, authentication and UI interactions using synthetic fixtures.
- [x] 3.2 [market-context-page] Run frontend test/lint/typecheck/build and targeted backend tests; inspect integrated diff and obtain independent review; validate OpenSpec and record limitations.
