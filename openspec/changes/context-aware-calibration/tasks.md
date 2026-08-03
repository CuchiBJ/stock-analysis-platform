## 1. Context-aware calibration backend

- [x] 1.1 [calibration-reporting] Add reusable cohort statistics, Wilson interval, and drift-classification helpers.
- [x] 1.2 [calibration-reporting] Extend the calibration endpoint with historical, 21-day recent, current-regime cohorts, and current market context while retaining legacy fields.
- [x] 1.3 [calibration-reporting] Add unit coverage for cohort thresholds, intervals, drift, and transition coverage.

## 2. Empirical probability wiring

- [x] 2.1 [context-aware-empirical-probability] Implement the regime/RS-aware empirical fallback ladder and expose the selected cohort basis.
- [x] 2.2 [context-aware-empirical-probability] Bulk-fetch prior metrics and pass each actionable candidate's actual transition and current regime into probability lookup.
- [x] 2.3 [context-aware-empirical-probability] Add unit coverage for fallback ordering, thresholds, and rule-based behavior.

## 3. Calibration presentation

- [x] 3.1 [calibration-reporting] Update frontend response types and render the compressed current-context evidence summary.
- [x] 3.2 [calibration-reporting] Replace the historical-only table with historical/recent/current-regime delivery and drift columns, including insufficient-sample copy and risk-first ordering.

## 4. Verification

- [x] 4.1 [calibration-reporting] Run backend tests, frontend type/build validation, and smoke the live calibration/actionable endpoints against local data.

## 5. As-of regime consistency

- [x] 5.1 [market-regime] Anchor all regime factor queries to one resolved as-of snapshot and add regression coverage.
- [x] 5.2 [market-context-consistency] Store and expose the as-of regime in MarketContext, then reuse it in Calibration and actionable scoring.
- [x] 5.3 [calibration-reporting] Add deterministic observation regime reclassification with cache invalidation and tests.

## 6. Baseline and posture alignment

- [x] 6.1 [calibration-reporting] Add the non-overlapping 180-day baseline cohort, drive drift from baseline versus recent, and update the Calibration table.
- [x] 6.2 [market-context-consistency] Always surface NOT_PAYING in posture reasons without raising defensive states, with regression tests.

## 7. Final verification

- [x] 7.1 [market-context-consistency] Run full backend tests, frontend build/typecheck, OpenSpec validation, regime reclassification, and live endpoint smoke checks.
