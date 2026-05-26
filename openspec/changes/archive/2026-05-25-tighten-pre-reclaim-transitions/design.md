## Context

Los 4 transitions pre-reclaim operan debajo de EMA21 y detectan patrones de agotamiento o recuperación antes de que el stock reclame. Actualmente ninguno exige quality gates ni límite inferior de profundidad.

## Goals / Non-Goals

**Goals:** Quality gates uniformes en todo el motor. Límite de -2.0 ATR como frontera entre "corrección sana" y "tendencia rota".

**Non-Goals:** No cambiar thresholds de volumen/RS ni la posición en la cascada.

## Decisions

### SUPPORT_HOLDING — redefinición semántica

El criterio actual (`-0.5 <= ema50 <= 0.2 and ema21_distance_change > 0.1`) puede disparar con el stock arriba de EMA21 (si ema50 es positivo y ema21 también). La nueva definición exige explícitamente `ema21 < 0` para que el nombre sea honesto: el stock está debajo de EMA21 y EMA50 lo sostiene.

### Límite -2.0 ATR para VOLUME_DRY_UP y COMPRESSING

Más allá de -2.0 ATR el stock está en territorio de tendencia rota, no de pullback institucional recuperable. FLUSH_AND_RECOVER ya tiene su propio límite (`-2.5 <= ema21 <= -0.5`), que se mantiene.

## Migration Plan

Editar los 4 blocks en `_determine_operational_transition()`:

```python
# 4. Flush and recover
if (self._is_quality_leader(current_metrics) and       # NEW
        rvol > 1.5 and ema21_distance_change > 0.3 and
        -2.5 <= ema21 <= -0.5):
    return OperationalTransition.FLUSH_AND_RECOVER

# 5. Volume dry-up
if (self._is_quality_leader(current_metrics) and       # NEW
        volume_change_pct < -25 and
        -2.0 <= ema21 < -0.3 and                       # CHANGED: added upper bound
        rs_change >= -1):
    return OperationalTransition.VOLUME_DRY_UP

# 6. Compressing
if (self._is_quality_leader(current_metrics) and       # NEW
        structure_change > 0.08 and
        -2.0 <= ema21 < -0.3 and                       # CHANGED: added upper bound
        volume_change_pct < 0):
    return OperationalTransition.COMPRESSING

# 8. Support holding
if (self._is_quality_leader(current_metrics) and       # NEW
        ema21 < 0 and                                  # NEW: must be below EMA21
        -0.5 <= ema50 <= 0.2 and
        ema21_distance_change > 0.1):
    return OperationalTransition.SUPPORT_HOLDING
```
