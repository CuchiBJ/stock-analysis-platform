## Why

Los conteos sectoriales actuales no permiten comparar sectores de tamaños distintos. El porcentaje de máximos entre eventos tampoco expresa participación sobre el universo elegible. Se necesita evidencia interpretable de concentración y cobertura, sin un nuevo score de mercado.

## What Changes

- Mostrar máximos y mínimos como conteo y porcentaje del universo elegible.
- Agregar cobertura por sector, incluyendo sectores sin eventos y sin cobertura.
- Comparar tasas sectoriales con barras de escala común y orden seleccionable.
- Resumir concentración de eventos en los dos sectores con más máximos/mínimos; mantener acciones desplegables.

## Capabilities

### New Capabilities
- `market-context-sector-breadth`: Comparación normalizada y concentración de extremos por sector.

### Modified Capabilities
Ninguna; extensión opt-in de la página dedicada.

## Impact

market_context_breadth agrega denominadores solo cuando include_constituents=True. Frontend extrae Extremes/StockList a SectorBreadth con helper y pruebas. Sin nuevas dependencias, queries por sector ni cambios /current.

## Non-goals

No modificar Dashboard, definición de extremos252 ruedas, reglas de postura, filtros de universo, vigencia, evolución ni explicaciones anteriores. No rankings de inversión, metadata histórica, ingesta o despliegue.
