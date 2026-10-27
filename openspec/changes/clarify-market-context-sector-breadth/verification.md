# Verification — sector breadth

Implemented locally; not deployed.

## Scope

- Backend: `market_context_breadth.py` adds opt-in eligible/excluded counts for every universe sector; `test_market_context_breadth.py` covers reconciliation and legacy behavior.
- Frontend: `SectorBreadth.tsx`, `market-context-sectors.ts`, and its tests; optional sector coverage type in `market-context.ts`; local extraction/integration in `MarketContextPage.tsx`.
- Primary agent specified behavior and reviewed integration. GPT-6-luna agents implemented backend/frontend; independent backend agent reviewed frontend arithmetic, leading to zero-total reconciliation and invalid-count safeguards.

## Checks

- Focused backend breadth/overview tests: 13 passed (34 existing warnings).
- Frontend tests, lint, production build, and typecheck passed; final primary-agent run: 47 tests passed.
- Browser QA used the actual component in an isolated local Next fixture with synthetic data, not production data or the full authenticated application.
- Verified visible fixed-scale bars, incidence 6/100 vs 3/10, concentration 12/15 = 80%, sorting by highs and lows, opening stock links and closing disclosure by keyboard.
- Visual review at desktop and 390px mobile width; corrected the paired bars to span both columns at all breakpoints.
- Baseline checksums confirm Dashboard bar/drawer, posture explanation, evidence, evolution, market posture policy, context engine and endpoint unchanged by this iteration. Page diff is limited to sector block extraction/integration.

## Limitations

- Ruff unavailable in the backend environment.
- Full authenticated end-to-end and production validation were not run.
- Sector metadata reflects current classification, explicitly explained in methodology.
- Existing unrelated and prior-iteration work remains uncommitted and preserved.
