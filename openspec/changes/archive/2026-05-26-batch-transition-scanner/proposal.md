## Why

El panel `/calibration` shipped hoy hace visible que **el sistema casi no observa**: 1 observación total en 3+ días porque `transition_engine.record_observation` se invoca solo on-demand desde `/actionable` y `/transitions/symbol/*`. Las cohortes nunca cruzan N≥5, el `EmpiricalProbabilityCalculator` siempre cae a rule-based, y el panel mostraría empty-state durante meses sin un fix.

La calibración no es útil sin volumen de observaciones. Este change agrega batch scanning: una vez por SLOW cycle, recorrer el universo de stocks con metrics recientes y registrar todas las transitions detectadas. Pasa de ~1 obs/día a ~50-200 obs/día (estimado conservador del % de stocks no-STABLE en momento dado).

## What Changes

- **Backend nuevo**: `backend/app/services/batch_transition_scanner.py`
  - Clase `BatchTransitionScanner(db: AsyncSession)`
  - Método `async scan_universe(as_of_date: date) -> ScanStats` que:
    1. Obtiene `latest_metrics_date` (debe coincidir con `as_of_date` o no scanea)
    2. Carga todos los `(Stock, StockMetrics)` joineados donde `StockMetrics.date == latest_metrics_date` y que pasen `QUALITY_FILTERS` (avg_volume_10d ≥ 500k, current_price ≥ $5, adr_percent ≥ 2%)
    3. Carga el `StockMetrics` previo más reciente para cada símbolo (una query agregada con ROW_NUMBER OVER PARTITION BY symbol)
    4. Por cada par (current, previous): llama `TransitionEngine.calculate_operational_transition` que internamente persiste la observación si transition ≠ STABLE
    5. Retorna stats `{scanned, non_stable_detected, recorded, errors, duration_sec}`
- **Scheduler wiring**: en `scheduler.py`, después de SLOW cycle completar y disparar `_evaluate_pending_outcomes`, también disparar `_batch_scan_transitions` (paralelo, fire-and-forget vía `asyncio.create_task`)
- **Endpoint admin opcional**: `POST /api/v1/calibration/scan-now` que dispara el scan manualmente (útil para testing y para forzar acumulación inicial sin esperar al SLOW cycle). Returns stats.
- **Sin cambios** a: `TransitionEngine`, `OutcomeTracker`, `EmpiricalProbabilityCalculator`, el shape de `transition_observations`. El recording ya existe — solo agregamos volumen de invocaciones.

## Capabilities

### New Capabilities
- `batch-transition-detection` — batch scan + observation recording sobre el universo completo

### Modified Capabilities
- (none)

## Impact

- **NEW**: `backend/app/services/batch_transition_scanner.py`
- **NEW**: `backend/tests/test_batch_transition_scanner.py`
- **MODIFIED**: `backend/app/data/scheduler.py` — agregar `_batch_scan_transitions` callable + invocación post-SLOW
- **MODIFIED**: `backend/app/api/v1/endpoints/calibration.py` — agregar `POST /scan-now`
- **Sin cambios al frontend**: la página `/calibration` se llena sola a medida que entran datos.

## Non-goals

- No persistir el predicted_probability_at_detection (out-of-sample calibration deferred — sigue siendo Phase 2).
- No paralelizar el scan con `asyncio.gather` (Phase 1 = serial, simple; ~1000 stocks × 30ms = 30s aceptable). Optimizar si en prod resulta lento.
- No introducir un tracking table `batch_scan_runs`. Logging es suficiente para Phase 1.
- No exponer el endpoint manual fuera de uso interno (sin auth pero con tag `admin`; backlog para auth real).
- No tocar QUALITY_FILTERS — usar el set existente. Si Fernando quiere relajar (más obs) o restringir (menos noise) se ajusta después.
- No skipear stocks que ya tienen observación para `date_detected = today`: el idempotency en `record_observation` (on_conflict_do_nothing por (symbol, transition_type, date_detected)) ya maneja el doble-trigger.
