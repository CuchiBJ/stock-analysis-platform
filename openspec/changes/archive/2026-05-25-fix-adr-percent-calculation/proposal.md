## Why

El campo `adr_percent` en `stock_metrics` está calculado con una fórmula incorrecta — mide **cambio close-to-close** en vez del **rango diario high-low** que es lo que el término ADR (Average Daily Range) significa en trading institucional. Esto produce valores sistemáticamente más bajos que el ADR real: MCHP reporta 2.26% (debería ~4-5%), ON reporta 3.18% (debería ~5-6%). Como consecuencia, large-caps institucionales que Minervini y momentum traders tradearían sin problema fallan los filtros de calidad del sistema (`_INSTITUTIONAL_SETUP` exige >= 4%). Viola Principio 7 (interpretabilidad — el valor reportado no corresponde a la métrica que dice ser) y Principio 9 (señal institucional primaria — el filtro elimina líderes institucionales reales).

## What Changes

- **Fórmula correcta en `calculate_adr_percent()`**: reemplazar `pct_change().abs().mean()` (close-to-close) por `((high - low) / close).mean() * 100` (rango diario real)
- **Firma de la función**: aceptar un DataFrame con columnas `high`, `low`, `close` en lugar de solo una Series de precios close
- **Caller en `metrics_calculator.py`**: pasar el DataFrame completo con high/low/close en vez de solo close_prices
- **Recalcular `stock_metrics.adr_percent`** para todos los símbolos usando la fórmula corregida
- **Re-evaluación post-recalculación**: el threshold actual de `>= 4.0%` en `_INSTITUTIONAL_SETUP` fue calibrado contra la fórmula incorrecta. Después de recalcular, validar contra MCHP y ON y ajustar si es necesario

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `universe-management`: el Requirement "Quality Filters SHALL Apply Uniformly" actualmente usa una métrica ADR sistemáticamente sesgada. La corrección de la fórmula hace que los filtros que dependen de `adr_percent` (en `universe_filters.py`, `transitions.py`, `quality_swing_scanner_service.py`, etc.) operen sobre valores correctos.

## Non-goals

- No cambiar el significado conceptual de `adr_percent` (sigue siendo porcentaje, sigue siendo ATR-equivalente de 20 días)
- No agregar columnas nuevas a `stock_metrics`
- No tocar otros cálculos de momentum (`calculate_relative_strength`, `calculate_atr`, etc.)
- No ajustar thresholds en otros servicios consumidores sin antes ver los valores post-recalculación
- No cambiar el período de cálculo (sigue siendo 20 días)

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/data/processors/momentum.py` | Reescribir `calculate_adr_percent()` con la fórmula correcta y firma nueva |
| `backend/app/data/ingestors/metrics_calculator.py` | Actualizar caller (línea 151) para pasar el DataFrame con high/low/close |
| `stock_metrics` (tabla) | Recalcular `adr_percent` para todos los símbolos vía script existente |
| `backend/app/api/v1/endpoints/transitions.py` | Posiblemente ajustar `_INSTITUTIONAL_SETUP` threshold si MCHP/ON siguen sin pasar (decisión basada en datos post-recalc) |

Sin migraciones de schema. Sin cambios de API. Cambio transparente para el frontend.
