## Why

El FAST metrics cycle (cada 5 min) cubre una lista estática de 200 símbolos TIER 1. Los stocks que aparecen en live transitions (entering_pullback, continuation_holding, etc.) pueden no estar en TIER 1, recibiendo métricas con 30-60 minutos de latencia. Durante ese tiempo el precio puede moverse significativamente y el feed muestra setups que ya rebotaron o se invalidaron.

El problema no es la frecuencia del ciclo — es que la cobertura del FAST cycle no está alineada con lo que el trader necesita observar. Un stock que pasó los 8 quality gates y está en el feed operativo ES por definición un candidato de alta prioridad, independientemente de su tier asignado.

Viola Principio 1 (transitions dominate — no se puede detectar una transición si los datos tienen 1 hora de latencia) y Principio 10 (workflow > analytics — el feed debe reflejar el estado actual del mercado, no el estado de hace 40 minutos).

## What Changes

El `trigger_fast_metrics_update()` en `scheduler.py` reemplaza la lista estática de TIER 1 por una lista dinámica que combina:

1. **Stocks en live transitions**: los símbolos que aparecen actualmente en el feed de transitions (calculados vía la query de `_INSTITUTIONAL_SETUP`)
2. **TIER 1 hardcoded**: los 200 símbolos actuales como base garantizada

La unión de ambas listas se recalcula en cada ciclo de 5 minutos. El resultado es que cualquier stock que pase los quality gates y esté en el feed operativo siempre tiene métricas frescas.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `universe-management`: el Requirement de FAST metrics coverage se amplía de "TIER 1 estático" a "TIER 1 + stocks en live transitions".

## Non-goals

- No cambiar la frecuencia del FAST cycle (sigue siendo cada 5 min).
- No cambiar la frecuencia del SLOW cycle (sigue siendo cada 30 min para todos).
- No modificar qué métricas calcula el FAST cycle (sigue usando `days=10`).
- No reemplazar el tier system — TIER 1 sigue siendo el baseline, los live transitions son un complemento dinámico.
- No agregar más de ~100 símbolos adicionales al FAST cycle (la query de institutional setup devuelve ~150 stocks, el overlap con TIER 1 reduce el incremento neto).

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/data/scheduler.py` | `trigger_fast_metrics_update()`: agregar query de stocks que pasan `_INSTITUTIONAL_SETUP` y unirlos con los TIER 1 |

Sin migración, sin schema, sin frontend.
