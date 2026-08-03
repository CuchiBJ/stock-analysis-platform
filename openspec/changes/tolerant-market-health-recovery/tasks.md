## 1. Pure health policy

- [x] 1.1 [market-health-recovery] Create `market_health.py` with severity constants, worst-case daily severity classification, and rolling repair diagnostics.
- [x] 1.2 [market-health-recovery] Implement health-state reduction with 5-clean-of-7 recovery, zero-severe-of-3 veto, and recent-severe ROBUST guard.

## 2. Market Context integration

- [x] 2.1 [market-health-recovery] Integrate severity and the extracted reducer into `MarketContextEngine` while preserving existing health fields and compatibility surfaces.
- [x] 2.2 [market-health-recovery] Add repair/severity diagnostics to `HealthAnalysis` and `/api/v1/market-context/current` serialization.
- [x] 2.3 [market-health-recovery] Update posture unlock text to explain rolling repair progress instead of five consecutive sessions.

## 3. Presentation

- [x] 3.1 [market-context-presentation] Extend frontend health types and render clean/mild/severe cells in the damage strip.
- [x] 3.2 [market-context-presentation] Show compact 5-of-7 repair progress, recent severe count, and updated explanatory copy in the bar/drawer.

## 4. Verification

- [x] 4.1 [market-health-recovery] Add regression tests for severity precedence, mild pullback tolerance, severe veto, robust guard, and additive posture/API semantics.
- [x] 4.2 [market-health-recovery] Run focused backend tests, frontend TypeScript validation, strict OpenSpec validation, and inspect the live Market Context response.
