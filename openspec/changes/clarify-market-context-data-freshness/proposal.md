## Why

La página concede el mismo peso a cotizaciones actuales y atrasadas, y confunde un cierre diario anterior del VIX con una falla de actualización. Esto dificulta una lectura interpretable del mercado y contradice la jerarquía visual por relevancia.

## What Changes

- Identificar la vigencia de precios e indicadores respecto de la fecha del contexto.
- Atenuar cotizaciones atrasadas sin ocultar sus valores y fechas.
- Mostrar cuándo SPY y QQQ no admiten comparación temporal.
- Separar la antigüedad del cierre VIX de una falla de actualización de su fuente.

## Capabilities

### New Capabilities
- `market-context-data-freshness`: Presentación explícita de vigencia y comparabilidad en la página dedicada.

### Modified Capabilities
Ninguna. Extensión aditiva de la página existente.

## Impact

Frontend de Market context y helpers; campo aditivo en la respuesta VIX y pruebas focalizadas. Sin nuevas dependencias.

## Non-goals

No modificar Dashboard, postura, pesos ni reglas; no corregir ingesta QQQ, ejecutar backfills, inferir feriados ni ofrecer cotizaciones en vivo. No desplegar esta iteración como parte de la implementación local.
