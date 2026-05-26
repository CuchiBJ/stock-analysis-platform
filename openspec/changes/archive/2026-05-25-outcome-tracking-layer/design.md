## Context

El sistema actualmente clasifica cada símbolo en una de las 12 `OperationalTransition` cada vez que `transition_engine.calculate_operational_transition()` corre (típicamente una vez por SLOW cycle por símbolo). El resultado se devuelve al endpoint `/transitions/live` y al feed del frontend, pero no se persiste excepto en `setup_state_log` que solo registra el `SetupState` (no el `OperationalTransition`) y es write-only — no se consulta para evolution analysis ni para outcome.

Los datos necesarios para evaluar outcomes ya existen: `stock_prices` tiene OHLCV diario por símbolo, `stock_metrics` tiene EMAs. La pieza faltante es (a) un registro de cada detección con context snapshot, (b) un evaluador que mire forward N días y compute outcome, (c) endpoints que agreguen.

## Goals / Non-Goals

**Goals:**
- Persistir cada detection significativa (no-STABLE) sin afectar performance del transition engine.
- Evaluar outcomes deterministically a partir de `stock_prices`.
- Permitir queries agregadas por transition × regime con sample_size visible.
- Schema lo suficientemente flexible para agregar transition types futuros sin migración.

**Non-Goals:**
- No backfill — empezamos forward.
- No ML / scoring calibration — datos primero.
- No exposición al frontend en este change.
- No tracking de STABLE (sería ruido — 80%+ del universo está STABLE en cualquier día).

## Decisions

### Decisión 1: Tabla nueva, no extender `setup_state_log`

`setup_state_log` registra `SetupState` (lifecycle, lento). `TransitionObservation` registra `OperationalTransition` (operational, rápido) + context snapshot + outcome. Son conceptos distintos. Mezclarlos rompe la separación setup_lifecycle vs transition_engine.

Tabla dedicada: `transition_observations`. Schema:

```sql
CREATE TABLE transition_observations (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    transition_type VARCHAR(40) NOT NULL,   -- enum como string para flexibilidad
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date_detected DATE NOT NULL,             -- date del stock_prices, no de detection
    -- context snapshot
    regime_at_detection VARCHAR(20),         -- bull/bear/volatile/neutral
    price_at_detection FLOAT,
    ema9_at_detection FLOAT,
    ema21_at_detection FLOAT,
    ema50_at_detection FLOAT,
    atr_at_detection FLOAT,                  -- crítico para evaluar drawdown en ATR units
    rs_spy_at_detection FLOAT,
    adr_percent_at_detection FLOAT,
    vcp_score_at_detection FLOAT,
    relative_volume_at_detection FLOAT,
    weekly_tightness_at_detection FLOAT,
    -- outcome fields (filled async)
    price_1d FLOAT,
    price_5d FLOAT,
    price_20d FLOAT,
    pct_1d FLOAT,
    pct_5d FLOAT,
    pct_20d FLOAT,
    max_gain_within_10d FLOAT,               -- pct del precio detection
    max_drawdown_within_10d FLOAT,           -- pct del precio detection (negativo)
    max_gain_atr_within_10d FLOAT,           -- ATR units desde detection
    max_drawdown_atr_within_10d FLOAT,       -- ATR units desde detection
    reached_ema21_within_10d BOOLEAN,
    broke_ema50_within_10d BOOLEAN,
    -- outcome classification
    outcome_status VARCHAR(20),              -- PENDING | SUCCESS | FAILURE | NEUTRAL | INSUFFICIENT_DATA
    outcome_evaluated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX ix_obs_symbol_type_date 
  ON transition_observations (symbol, transition_type, date_detected);

CREATE INDEX ix_obs_pending 
  ON transition_observations (outcome_status, date_detected) 
  WHERE outcome_status = 'PENDING';

CREATE INDEX ix_obs_aggregation 
  ON transition_observations (transition_type, regime_at_detection, outcome_status);
```

Alternativa descartada: agregar columnas a `setup_state_log`. Mezcla conceptos, requiere agregar lifecycle vs transition discriminator, complica queries.

### Decisión 2: Dedup por (symbol, transition_type, date_detected)

Mismo símbolo en mismo estado en mismo día = 1 observation. Si el scheduler corre el SLOW cycle dos veces el mismo día (puede pasar en debugging), no duplicamos. Implementación: `INSERT ... ON CONFLICT DO NOTHING` o check-then-insert.

Alternativa descartada: dedup por (symbol, transition_type, detected_at hourly). Demasiado granular — un cambio de NVDA a VOLUME_DRY_UP a las 10am y 11am es la misma observación.

### Decisión 3: Outcome evaluation deferred — corre después de SLOW cycle

`record_observation` solo escribe context snapshot. `evaluate_pending_outcomes(as_of_date)` corre como background task después de cada SLOW cycle exitoso. Query:

```sql
SELECT * FROM transition_observations 
WHERE outcome_status = 'PENDING' 
  AND date_detected <= :as_of - INTERVAL '1 day'  -- al menos 1 día transcurrido
```

Por cada observation pendiente:
- Si `date_detected + 1d <= as_of`: fill `price_1d`, `pct_1d`
- Si `date_detected + 5d <= as_of`: fill `price_5d`, `pct_5d`
- Si `date_detected + 10d <= as_of`: fill `max_gain_within_10d`, `max_drawdown_within_10d`, `reached_ema21_within_10d`, `broke_ema50_within_10d`, y CLASIFICAR `outcome_status`.
- Si `date_detected + 20d <= as_of`: fill `price_20d`, `pct_20d`.

Una observation queda PENDING hasta tener +10d de data (necesario para clasificación). Después de +20d, fields completos pero outcome_status ya fijado a +10d.

### Decisión 4: Success definition explícita por familia

Implementada en `OutcomeTracker._classify_outcome(observation)`:

```python
PRE_RECLAIM = {ENTERING_PULLBACK, VOLUME_DRY_UP, COMPRESSING, 
               FLUSH_AND_RECOVER, SUPPORT_HOLDING}
RECLAIM_CONT = {RECLAIMING, CONTINUATION_HOLDING, STABILIZING}
DETERIORATION = {WEAKENING, DISTRIBUTION, FAILING}

def _classify_outcome(obs):
    t = obs.transition_type
    drawdown_atr = obs.max_drawdown_atr_within_10d
    gain_atr = obs.max_gain_atr_within_10d
    
    if t in PRE_RECLAIM:
        if obs.broke_ema50_within_10d or drawdown_atr < -3.0:
            return FAILURE
        if obs.reached_ema21_within_10d and drawdown_atr > -2.5:
            return SUCCESS
        return NEUTRAL
    
    if t in RECLAIM_CONT:
        if obs.pct_5d is not None and obs.pct_5d < -3.0:  # rompió thesis
            return FAILURE
        if gain_atr is not None and gain_atr > 1.0 and (drawdown_atr or 0) > -1.5:
            return SUCCESS
        return NEUTRAL
    
    if t in DETERIORATION:
        # inverted: avoiding = success
        if obs.pct_5d is not None and obs.pct_5d > 3.0:  # false signal
            return FAILURE
        if obs.pct_10d is not None and obs.pct_10d < 0:
            return SUCCESS
        return NEUTRAL
    
    return NEUTRAL
```

Estos thresholds son **first-pass calibration** basados en intuición de magnitude. Una vez tengamos ≥1000 observaciones, podremos ajustarlos contra distribución empírica.

### Decisión 5: Aggregation endpoint con sample_size mínimo

```
GET /api/v1/transitions/track-record?transition_type=ENTERING_PULLBACK&regime=bull&days=90
```

Response:
```json
{
  "transition_type": "ENTERING_PULLBACK",
  "regime": "bull",
  "window_days": 90,
  "sample_size": 47,
  "success_rate": 0.638,
  "failure_rate": 0.149,
  "neutral_rate": 0.213,
  "avg_pct_5d": 2.3,
  "avg_max_gain_atr_10d": 1.8,
  "avg_max_drawdown_atr_10d": -1.2,
  "median_pct_5d": 1.9,
  "insufficient_data": false,
  "minimum_sample_warning": null
}
```

Si `sample_size < 30`, devolver `minimum_sample_warning: "Sample size below 30 — stats unreliable"`. No bloqueamos response; el caller decide qué hacer.

### Decisión 6: Regime snapshot lookup en `record_observation`

`regime_at_detection` requiere consultar `MarketRegimeEngine` en el momento. Para no agregar latencia al transition_engine, cacheamos el regime del día en memoria (módulo-level dict `{date: regime_string}`). Se invalida al cambiar de día.

Alternativa descartada: dejar `regime_at_detection` nullable y fillearlo en `evaluate_pending_outcomes`. Pero el regime puede cambiar entre detección y evaluation — perderíamos contexto verdadero.

## Risks / Trade-offs

**[Riesgo 1: Volume de observations explota si pre-reclaim transitions ocurren muchas veces para mismo símbolo]**
→ Mitigación: dedup por (symbol, transition_type, date_detected). Máximo 12 observations × 2761 stocks × 252 días = ~8.3M filas/año en worst case absoluto, pero realmente será <50K/año porque la mayoría de stocks está STABLE.

**[Riesgo 2: `evaluate_pending_outcomes` consulta stock_prices por símbolo y puede ser lento]**
→ Mitigación: bulk fetch — un solo query que trae todos los prices del rango (max_date - 25d, max_date) y join in-memory.

**[Riesgo 3: Definiciones de success son arbitrarias en first-pass]**
→ Aceptado. El propósito de este change es **empezar a medir**. Recalibration es trabajo futuro con datos en mano.

**[Riesgo 4: regime cache puede dar stale data si MarketRegimeEngine cambia entre detection y query]**
→ Aceptado. El regime se actualiza pocas veces por día. Vale más capturar el regime al momento de detección que recompute después.

**[Riesgo 5: Wire en transition_engine agrega DB write por cada clasificación]**
→ Mitigación: dedup query es índice unique → fast. Write es small (~200 bytes). Para 2761 símbolos × 1 SLOW cycle = ~2761 escrituras de los cuales ~80% van a hacer no-op por STABLE filter + dedup. Negligible.

## Migration Plan

1. Crear migración Alembic con tabla + 3 índices.
2. Implementar modelo SQLAlchemy.
3. Implementar `OutcomeTracker` con `record_observation` y `evaluate_pending_outcomes`.
4. Wire en `transition_engine.calculate_operational_transition`: después del return, llamar `await tracker.record_observation(...)` if transition != STABLE.
5. Wire en `scheduler._scheduler_loop`: después de SLOW cycle exitoso, schedular `await tracker.evaluate_pending_outcomes(today)`.
6. Agregar endpoints `/track-record` y `/observations/{symbol}` en `transitions.py`.
7. Aplicar migración. Sistema empieza a registrar observations en el próximo SLOW cycle.
8. Esperar ≥10 días para datos significativos. Esperar ≥90 días para sample sizes accionables.

**Rollback**: revertir código + drop table. Sin pérdida (todavía no es load-bearing).

## Open Questions

- ¿Capturamos `setup_quality` y `pullback_quality_score` también en el snapshot? Decisión actual: sí incluir `vcp_score` y `weekly_tightness` que son los más interpretables. Otros pueden agregarse después si se necesitan para análisis (ALTER TABLE, no migration painful).
- ¿Cuándo expirar observations? Por ahora ninguno — keep all forward. Si en 3 años hay >500K filas, evaluar archive strategy.
