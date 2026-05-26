## 1. Backend: batch_transition_scanner service

- [ ] 1.1 Create `backend/app/services/batch_transition_scanner.py` exposing class `BatchTransitionScanner(db: AsyncSession)` and dataclass `ScanStats(scanned, non_stable_detected, recorded, errors, duration_sec, as_of_date)`
- [ ] 1.2 Implement `async scan_universe(as_of_date: date) -> ScanStats`:
  - Validate `as_of_date` matches `max(stock_metrics.date)`
  - Query current metrics with `QUALITY_FILTERS` applied (`JOIN Stock ON ...`)
  - Query previous metrics in a single window query (ROW_NUMBER OVER PARTITION BY symbol ORDER BY date DESC LIMIT 1 per symbol, where date < as_of_date)
  - For each `(curr, prev)` pair (ordered by symbol): try `TransitionEngine.calculate_operational_transition`; on exception log + increment errors
  - Tally `non_stable_detected` and `recorded` (recorded == non_stable_detected when no idempotency collisions; we can't easily distinguish so report `recorded = non_stable_detected` as upper bound)
  - Return stats with duration measured from `time.monotonic()`

## 2. Scheduler wiring

- [ ] 2.1 In `backend/app/data/scheduler.py`, add method `async _batch_scan_transitions()` mirroring `_evaluate_pending_outcomes` pattern (open own session, instantiate scanner, call scan_universe, log result, swallow exceptions)
- [ ] 2.2 Inside `trigger_metrics_update`, after the existing `asyncio.create_task(self._evaluate_pending_outcomes())` line, add `asyncio.create_task(self._batch_scan_transitions())`

## 3. Manual endpoint

- [ ] 3.1 In `backend/app/api/v1/endpoints/calibration.py`, add `POST /scan-now` accepting optional query param `as_of_date: date | None`
- [ ] 3.2 Resolve as_of_date (param or max(stock_metrics.date)); return 404 with `"No stock_metrics data available"` if none
- [ ] 3.3 Run scanner, return stats as JSON

## 4. Tests

- [ ] 4.1 Create `backend/tests/test_batch_transition_scanner.py` with unit tests for the helper logic (constructing the query, dataclass shape). Skip full integration test (requires DB fixture).
- [ ] 4.2 Pure-function test: assert `ScanStats` defaults and field names

## 5. Smoke + verification

- [ ] 5.1 Restart backend; `curl -X POST http://localhost:8000/api/v1/calibration/scan-now` → verify stats returned, status 200
- [ ] 5.2 Re-query `/api/v1/calibration/by-transition-type` and confirm `total_observations` jumped
- [ ] 5.3 Run scanner a 2nd time → confirm `recorded` doesn't double (idempotency holds)
- [ ] 5.4 Visit `/calibration` page → confirm now shows pending observations breakdown

## 6. Validate + archive

- [ ] 6.1 Run `openspec validate batch-transition-scanner --type change --strict`
- [ ] 6.2 Archive `openspec archive batch-transition-scanner --yes`
- [ ] 6.3 Save memory entry; commit + push
