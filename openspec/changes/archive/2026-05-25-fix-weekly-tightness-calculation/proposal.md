## Why

El campo `weekly_tightness` en `stock_metrics` está calculado de forma invertida: stocks inactivos con volumen cero obtienen scores cercanos a 1.0 (perfecta tightness) porque su rango semanal es cero, mientras que stocks institucionales de alta calidad (LITE, AXTI, VICR) obtienen 0.03–0.10. Esto corrompe silenciosamente todos los servicios que consumen esta métrica: el scanner no devuelve resultados institucionales, el lifecycle engine no detecta correctamente el estado TIGHTENING, y el invalidation engine rechaza setups válidos. Viola Principio 7 (interpretabilidad) y Principio 9 (señal institucional primaria).

## What Changes

- **`metrics_calculator.py` — fórmula `_calculate_weekly_tightness()`**: Dos correcciones quirúrgicas:
  1. Filtrar semanas con `volume == 0` antes de calcular el rango. Si quedan menos de 3 semanas activas en las últimas 4, retornar `0.0`.
  2. Normalizar el rango semanal por ATR diario (en lugar de por precio de cierre). `range_in_atr = weekly_range_dollars / daily_atr_mean`.
- **`quality_swing_scanner_service.py` — threshold**: Restaurar de `> 0.02` (parche de emergencia) a `> 0.3` (valor original diseñado para la escala ATR-norm).
- **Recalcular métricas**: Correr `scripts/recalculate_metrics_with_atr.py` para repoblar `stock_metrics` con los valores corregidos.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `universe-management`: El Requirement "Quality Filters SHALL Apply Uniformly" se extiende — `weekly_tightness` ahora es una métrica confiable que puede usarse como filtro real en el scanner (threshold `> 0.3` restaurado).

## Non-goals

- No cambiar los thresholds en `setup_lifecycle_engine`, `setup_invalidation_engine`, `pullback_service`, `ma_analyzer`, ni ningún otro servicio consumidor — la normalización ATR hace que los thresholds existentes sean correctos sin tocarlos.
- No cambiar el esquema de la base de datos ni agregar columnas.
- No recalcular métricas de stocks que no tienen datos históricos de precio.

## Impact

| Archivo | Tipo de cambio |
|---|---|
| `backend/app/data/ingestors/metrics_calculator.py` | Fix fórmula `_calculate_weekly_tightness()` |
| `backend/app/services/quality_swing_scanner_service.py` | Restaurar threshold `> 0.3` |
| `stock_metrics` (tabla) | Repoblación vía script existente |

Todos los servicios que consumen `weekly_tightness` se benefician automáticamente al recalcular. No hay cambios de API, no hay migraciones.
