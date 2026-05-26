## 1. DB: scheduler_errors table

- [ ] 1.1 Generate Alembic migration: `alembic revision -m "add_scheduler_errors"`
- [ ] 1.2 Create `scheduler_errors` table: id PK, task_name VARCHAR(100), exception_type VARCHAR(100), exception_message TEXT, traceback TEXT, occurred_at TIMESTAMP DEFAULT NOW(), resolved BOOLEAN DEFAULT FALSE; index on occurred_at DESC
- [ ] 1.3 Add `SchedulerError` model in `backend/app/models/stock.py` (same file as TransitionObservation, avoid new file for one model)
- [ ] 1.4 `alembic upgrade head`

## 2. Task error tracker

- [ ] 2.1 Create `backend/app/services/task_error_tracker.py` with `track_task_errors(task_name: str)` decorator returning an async wrapper
- [ ] 2.2 Wrapper does `try/except Exception`: persist to scheduler_errors via own `AsyncSessionLocal()`, log ERROR; on persistence failure log stderr and continue
- [ ] 2.3 Apply decorator to scheduler async tasks: `_evaluate_pending_outcomes`, `_batch_scan_transitions`, `_broadcast_metrics_updated`, `_run_realtime_discovery`, `_run_discovery_scans`, `_reevaluate_tiers`, `_run_health_check`, `_run_lifecycle_tracking`

## 3. Health endpoint

- [ ] 3.1 Create `backend/app/api/v1/endpoints/health.py` with router prefix `/health`
- [ ] 3.2 Implement `GET /data-freshness`: query `max(stock_metrics.date)`, `max(stock_price.date)`, count + sample of `scheduler_errors` last 24h
- [ ] 3.3 Compute `metrics_lag_days = (price_latest - metrics_latest).days`, `is_stale = metrics_lag_days > 0`
- [ ] 3.4 Compute `today_et` (US/Eastern), `is_weekday`
- [ ] 3.5 Build `warnings` array
- [ ] 3.6 Register router in `backend/app/api/v1/api.py`
- [ ] 3.7 Add startup cleanup: delete `scheduler_errors WHERE occurred_at < NOW() - 7d` (in `app/main.py` lifespan)

## 4. CLI script

- [ ] 4.1 Create `backend/scripts/health_check.py`: import the same logic as the endpoint, print JSON, exit code 0/1
- [ ] 4.2 Manual test: `python scripts/health_check.py` → JSON output

## 5. Frontend banner

- [ ] 5.1 Create `frontend/components/layout/DataHealthBanner.tsx`: client component, fetches `/api/v1/health/data-freshness` on mount + every 60s
- [ ] 5.2 Conditional rendering: red if `recent_errors_24h > 0`, amber if `is_stale`, hidden if both clean
- [ ] 5.3 Mount inside `DashboardLayout.tsx` above the nav

## 6. Verification

- [ ] 6.1 `curl localhost:8000/api/v1/health/data-freshness | jq` → shape correct
- [ ] 6.2 Force an error: insert manually via SQL → banner appears
- [ ] 6.3 `python scripts/health_check.py` → exits 0 when healthy
- [ ] 6.4 `npx tsc --noEmit` clean
- [ ] 6.5 `openspec validate data-health-surface --type change --strict`

## 7. Archive

- [ ] 7.1 `openspec archive data-health-surface --yes`
- [ ] 7.2 Memory entry + commit + push
