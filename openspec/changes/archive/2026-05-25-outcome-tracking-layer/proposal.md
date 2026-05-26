## Why

El sistema detecta transitions (ENTERING_PULLBACK, VOLUME_DRY_UP, COMPRESSING, FLUSH_AND_RECOVER, etc.) y persiste estado en `setup_state_log`, pero **nunca registra qué pasó después de la detección**. Sin esto:

- No podemos decir "ENTERING_PULLBACK funciona 60% en bull, 15% en bear" porque nunca lo medimos.
- Cada threshold (perf_1y > 30%, adr >= 3%, score >= 70) es intuición codificada, no calibración contra outcomes reales.
- El sistema no puede mejorar — el scoring nunca aprende.
- Violamos Principio 7 (Interpretability over prediction): mostramos scores sin track record.

Esto fue identificado como **PRIORITY 1 #1** en la auditoría institucional. Es la **base sobre la cual el resto del producto pasa de "screener con narrative" a "edge engine medible"**.

## What Changes

- Nueva tabla `transition_observations` que persiste cada detección de transition (no-STABLE) con context snapshot completo en el momento.
- Nuevo servicio `OutcomeTracker`:
  - `record_observation(symbol, transition, current_metrics, regime)` — llamado desde transition engine después de cada clasificación. Dedup: 1 por (symbol, transition_type, date_detected).
  - `evaluate_pending_outcomes(as_of_date)` — job async diario que llena outcome fields para observaciones con suficiente tiempo transcurrido (>=1d, >=5d, >=20d).
- Definición de éxito **por familia de transition**:
  - **Pre-reclaim**: SUCCESS si alcanzó EMA21 en 10d AND max_drawdown > -2.5 ATR. FAILURE si rompió EMA50 o drawdown < -3 ATR.
  - **Reclaim/continuation**: SUCCESS si max_gain > +1 ATR en 5d AND drawdown > -1.5 ATR. FAILURE si rompió EMA21.
  - **Deterioration** (inverted): SUCCESS si precio cerró menor en 10d. FAILURE si rebotó >3% en 5d (false signal).
- Integración en `transition_engine.py`: llamar `record_observation` después de cada classification != STABLE.
- Integración en `scheduler.py`: correr `evaluate_pending_outcomes` después del SLOW cycle.
- Nuevo endpoint `GET /api/v1/transitions/track-record` con query params `transition_type`, `regime`, `days` — devuelve sample_size, success_rate, avg_gain_5d, avg_drawdown_5d, distribución.
- Nuevo endpoint `GET /api/v1/transitions/observations/{symbol}` — historia de observations del símbolo.

## Capabilities

### New Capabilities
- `outcome-tracking`: persistencia de detecciones, evaluación de outcomes, y agregación de track record por transition × regime

### Modified Capabilities
- `transition-engine`: ahora persiste cada clasificación significativa como observation con snapshot completo

## Non-goals

- Sin frontend en este change. UI vendrá en un change separado una vez tengamos ≥90 días de observaciones (sample size mínimo).
- Sin backfill retroactivo. El sistema no tiene historia de detecciones — empezamos tracking forward.
- Sin ML / probability calibration. Stats crudos primero.
- Sin alertas basadas en track record ("transition con X% follow-through"). Pure measurement, sin action.
- Sin dashboard de performance. El track-record endpoint es para consumo interno / análisis.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/alembic/versions/XXX_create_transition_observations.py` | Nueva migración con tabla `transition_observations` + índices |
| `backend/app/models/stock.py` | Modelo `TransitionObservation` con context + outcome fields |
| `backend/app/services/outcome_tracker.py` | Nuevo servicio (`record_observation`, `evaluate_pending_outcomes`, success classifiers) |
| `backend/app/services/transition_engine.py` | Hook después de clasificación: llamar `record_observation` |
| `backend/app/data/scheduler.py` | Wire `evaluate_pending_outcomes` después de cada SLOW cycle |
| `backend/app/api/v1/endpoints/transitions.py` | Nuevos endpoints `/track-record` y `/observations/{symbol}` |

**Growth implications**: ~50 observations/día × 365 = ~18K filas/año. Negligible. Index en (symbol, date_detected) y (transition_type, regime_at_detection, outcome_status).

**Performance**: `evaluate_pending_outcomes` consulta `stock_prices` por símbolo para cada observation pendiente — batched, debería correr en <30s para típico volumen.
