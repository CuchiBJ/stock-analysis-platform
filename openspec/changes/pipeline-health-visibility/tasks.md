## 1. Backend — modelo y persistencia [data-health-monitoring]

- [x] 1.1 Crear modelo `PipelineHeartbeat` en `backend/app/models/stock.py` (o nuevo `pipeline.py`) con columnas: `cycle_name` (str, PK), `last_run_at` (datetime), `last_success_at` (datetime, nullable), `last_duration_seconds` (float), `symbols_processed` (int, nullable), `symbols_expected` (int, nullable), `status` (Enum `ok`/`partial`/`failed`), `last_error_message` (text, nullable), `updated_at` (datetime, onupdate=now)
- [x] 1.2 Generar migración Alembic (manual: `a7e1b9c2d4f0_add_pipeline_heartbeats.py`, down_revision=`930904ebf606`)
- [ ] 1.3 Aplicar migración en local y verificar tabla creada con `\d pipeline_heartbeats`
- [x] 1.4 Crear helper `backend/app/data/pipeline_heartbeat.py` con `async def record_cycle(...)`. Upsert PG `ON CONFLICT`, log WARNING en fallo, no re-raise
- [x] 1.5 Reglas para `last_success_at`: sólo se actualiza si `status="ok"`; en `partial`/`failed` se preserva el anterior

## 2. Backend — instrumentar scheduler [data-health-monitoring]

- [x] 2.1 Instrumentado bloque price update con `_record_heartbeat("price", ...)`
- [x] 2.2 Instrumentado bloque FAST metrics (chained y standalone) con `_record_heartbeat("fast_metrics", ...)` usando `symbols_processed=count`
- [x] 2.3 Instrumentado bloque SLOW metrics con `_record_heartbeat("slow_metrics", ...)`, `symbols_expected` vía `_count_slow_expected()`, status `partial` si < 95%
- [x] 2.4 Instrumentado `_run_realtime_discovery` con try/finally + `_record_heartbeat("realtime_discovery", ...)`
- [x] 2.5 Instrumentado bloque post-close cycle con `_record_heartbeat("post_close_cycle", ...)`
- [ ] 2.6 Smoke test manual (deferred — requiere correr scheduler local)

## 3. Backend — endpoint y market state [data-health-monitoring]

- [x] 3.1 `MARKET_WARMUP_END_ET = time(10, 30)` y `compute_market_state(now_et)` en `health.py`
- [x] 3.2 `_heartbeats(db)` agrega `age_seconds` y mapea cada `PipelineHeartbeat` a dict
- [x] 3.3 `_coverage(db, now_et)` con QUALITY_FILTERS + `StockMetrics.updated_at >= market_open_utc`
- [x] 3.4 `market_state` integrado en el snapshot
- [x] 3.5 Verificar manualmente con `curl http://localhost:8000/api/v1/health/data-freshness | jq` → coverage de cohorte fija `618/619 (99.8%)`
- [x] 3.6 Corregir coverage para que `expected` y `actual` usen la misma cohorte quality de la última sesión completa

## 4. Backend — tests [data-health-monitoring]

- [x] 4.1 `test_record_cycle_ok_includes_last_success_at_in_update` — verifica upsert con SET incluye last_success_at
- [x] 4.2 `test_record_cycle_partial_omits_last_success_update` — partial preserva el last_success_at anterior
- [x] 4.3 `test_record_cycle_db_failure_does_not_raise` — DB exception → rollback awaited, no re-raise
- [x] 4.4 8 casos `compute_market_state` (pre_market / warmup / boundary / regular / after_hours / closed / sábado)
- [ ] 4.5 Test de integración del endpoint (deferred — el repo no tiene async-DB fixtures; el chequeo manual cubre 8.1)
- [x] 4.6 Test de regresión: cambios intradía en QUALITY_FILTERS no se contabilizan como fallos de refresh

## 5. Frontend — tipos y data layer [data-health-monitoring]

- [x] 5.1 `frontend/types/health.ts` con `PipelineHeartbeat`, `Coverage`, `MarketState`, `HealthSnapshot`, `CycleStatus`, `SessionPhase`
- [x] 5.2 `frontend/hooks/usePipelineHealth.ts` con TanStack Query, refetchInterval 30s
- [x] 5.3 `DataHealthBanner.tsx` refactor — usa el hook, elimina state/interval propios

## 6. Frontend — chip [data-health-monitoring]

- [x] 6.1 `frontend/components/layout/PipelineHealthChip.tsx` — dot + coverage % + warmup badge
- [x] 6.2 `computeChipColor` en `pipelineHealthUtils.ts` (worst-case red/amber/green)
- [x] 6.3 Chip integrado en `DashboardLayout.tsx` al lado del logo
- [x] 6.4 `useState<boolean>` para abrir/cerrar drawer

## 7. Frontend — drawer [data-health-monitoring]

- [x] 7.1 `PipelineHealthDrawer.tsx` — fixed positioning + backdrop + sheet derecha (420px)
- [x] 7.2 Bloque Coverage con progress bar coloreada por threshold (red <80, amber <95, green ≥95)
- [x] 7.3 Bloque Cycles con `formatRelativeTime` + duration; sub-progress bar si `symbols_processed/expected`
- [x] 7.4 `CYCLE_STALE_THRESHOLDS_S` + `isCycleStaleByAge` aplican dot amber + label "stale" por edad
- [x] 7.5 Bloque Market state con phase, minutes_since_open, banner amber durante warmup
- [x] 7.6 Bloque Recent errors con task/exception/age + mensaje truncado
- [x] 7.7 Botón X + cierre con Escape + cierre con click en backdrop

## 8. Verification

- [ ] 8.1 Levantar backend + scheduler + frontend en local. Verificar chip verde en header con coverage real (deferred — user-driven smoke)
- [ ] 8.2 Forzar `status="partial"` insertando manualmente en DB; verificar chip amber y barra de coverage parcial (deferred)
- [ ] 8.3 Forzar error decorando una task con raise; verificar chip rojo y entry en recent_errors (deferred)
- [x] 8.4 Cubierto vía test unitario `compute_market_state` (cubre warmup, sábado, regular, etc.)
- [x] 8.5 `openspec validate pipeline-health-visibility --strict` → valid
- [x] 8.6 `pytest tests/test_pipeline_health.py` → 11/11 pass; frontend `tsc --noEmit` → sin errores
