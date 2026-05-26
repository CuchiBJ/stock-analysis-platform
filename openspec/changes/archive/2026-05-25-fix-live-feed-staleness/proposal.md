## Why

El live transition feed muestra señales del día anterior como si fueran actuales. NBIS fue un setup válido el 20/5 (acercándose a EMA21 con distancia decreciente), pero el 21/5 rebotó fuerte y ya no está en zona de entry. Sin embargo, el feed del 21/5 sigue mostrándolo porque la query busca en los últimos 7 días y toma la row más reciente que alguna vez pasó el filtro EMA — que es la del 20/5. Esto viola Principio 7 (interpretabilidad — el feed muestra datos falsos como si fueran actuales) y Principio 10 (workflow > analytics — un trader que ve NBIS el 21/5 basaría una decisión en datos obsoletos).

## What Changes

- **`get_live_transitions()` en `transitions.py`**: el endpoint pasa a usar dos queries en lugar de una:
  1. Query rápida para obtener `latest_date = MAX(date)` de `stock_metrics`
  2. Query principal restringida a `date >= latest_date - 1 día` — garantiza que el "current" de cada símbolo sea del día más reciente disponible en la DB, y que "previous" sea el día anterior para calcular la dirección

La query actual con `cutoff_date = now - 7 días` se reemplaza por la ventana de 2 días.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `transition-engine`: el Requirement "Live Feed SHALL Only Show Current-Day Setups" se agrega — la frescura de los datos es parte del contrato del feed.

## Non-goals

- No cambiar la lógica del transition engine
- No cambiar el schema de respuesta del endpoint
- No agregar datos intradiarios
- No tocar ningún otro endpoint
- No cambiar `_ACTIONABLE_FILTER`, `_INSTITUTIONAL_SETUP`, ni los triggers EMA

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/api/v1/endpoints/transitions.py` | Reemplazar `cutoff_date = now - 7 días` por ventana de 2 días anclada a `MAX(date)` |

Sin migraciones, sin cambios de schema, sin dependencias nuevas.
