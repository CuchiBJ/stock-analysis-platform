## 1. Backend: calibration endpoint

- [ ] 1.1 Create `backend/app/api/v1/endpoints/calibration.py` with router `prefix='/calibration'`
- [ ] 1.2 Implement `GET /by-transition-type` that:
  - Iterates `OperationalTransition` enum (excluding `STABLE`)
  - For each value, queries `transition_observations` grouped by `outcome_status`
  - Computes `n_resolved`, `success_count`, `failure_count`, `n_pending`, `success_rate`, `status`
  - Returns `{rows: [...], min_samples_required: 5, total_observations, total_resolved, total_pending, eta_first_data}`
- [ ] 1.3 Use a single query with `CASE WHEN` or two queries (one for resolved counts, one for pending counts) — choose whichever is simpler
- [ ] 1.4 Sort rows by `(status_order, n_resolved desc)` where `status_order = {'empirical': 0, 'insufficient': 1, 'no_data': 2}`
- [ ] 1.5 Compute `eta_first_data` only when `total_resolved == 0 and total_pending > 0`: query `min(date_detected)` of pending rows, add 10 days
- [ ] 1.6 Register the router in `backend/app/api/v1/api.py`

## 2. Backend: tests

- [ ] 2.1 Create `backend/tests/test_calibration_endpoint.py` with cases:
  - Empty DB → all rows `status='no_data'`, `total_resolved=0`, `eta_first_data` absent (no pending)
  - Only PENDING rows → `no_data` rows, `eta_first_data` present
  - Mixed: 6 entering_pullback resolved (4 SUCCESS, 2 FAILURE) → row shows `status='empirical'`, `success_rate=0.6667`
  - 3 resolved → `status='insufficient'`, `success_rate=null`
  - All transition types present in response
- [ ] 2.2 Run `pytest tests/test_calibration_endpoint.py -v`

## 3. Frontend: calibration page

- [ ] 3.1 Create `frontend/app/calibration/page.tsx` (App Router, 'use client')
- [ ] 3.2 Define `CalibrationRow` and `CalibrationResponse` interfaces matching the backend shape
- [ ] 3.3 Fetch from `${API_URL}/api/v1/calibration/by-transition-type` on mount
- [ ] 3.4 Render header card:
  - If `total_resolved === 0`: "Sistema observando" message + `total_observations`, `total_pending`, `eta_first_data`
  - If `total_resolved > 0`: stats summary line with totals + count of empirical rows
- [ ] 3.5 Render table with columns: transition_type | n_resolved | success_rate | status badge | note
  - `success_rate` formatted as percentage with 1 decimal when not null, `—` otherwise
  - Status badge: green for `empirical`, amber for `insufficient`, gray for `no_data`
  - Note column: `insufficient` rows show "Need X more"; `no_data` shows "no observations yet"; `empirical` rows show success/failure split

## 4. Frontend: navigation

- [ ] 4.1 Add "Calibration" link to `DashboardLayout.tsx` nav (same pattern as `/queue` and `/guide`)

## 5. Smoke + validation

- [ ] 5.1 Restart backend if running; hit `curl localhost:8000/api/v1/calibration/by-transition-type | jq` and verify shape
- [ ] 5.2 Open `/calibration` in browser; verify empty-state copy is correct with current DB state (1 pending observation)
- [ ] 5.3 Verify all 11 non-STABLE transition types appear in the table
- [ ] 5.4 Run `cd frontend && npx tsc --noEmit` — expect zero errors
- [ ] 5.5 Run `openspec validate calibration-feedback-loop --strict`

## 6. Archive

- [ ] 6.1 `openspec archive calibration-feedback-loop --yes`
- [ ] 6.2 Save memory entry for shipped change
