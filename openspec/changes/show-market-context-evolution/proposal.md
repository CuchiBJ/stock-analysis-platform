## Why

La página explica la postura actual, pero todavía obliga a leer registros para distinguir una mejora aislada de una reparación sostenida. Una evolución compacta debe hacer visibles las transiciones y recaídas sin inventar historia ni nuevas decisiones.

## What Changes

- Bloque alineado por fecha de amplitud, cantidad de líderes y severidad de daño, hasta 20 sesiones disponibles.
- Selección accesible de sesión con valores exactos y cobertura explícita.
- Datos faltantes como huecos, sin interpolación ni arrastre de valores.

## Capabilities

### New Capabilities
- `market-context-evolution`: Evolución fechada de la evidencia existente en la página dedicada.

### Modified Capabilities
Ninguna.

## Impact

Campo aditivo evolution en /overview con 20 sesiones reales de amplitud y cantidad de líderes, preservando nulos. Método público acotado del engine y serializador aislado; frontend helper, componente, pruebas e inserción en MarketContextPage. Severidad usa health.series. /current conserva historial de 10 puntos. Sin dependencias.

## Non-goals

No historia de postura (el contrato no la ofrece), densidad histórica (solo hay cantidad de líderes), SPY/QQQ/VIX históricos, score de recuperación, cambios de política, Dashboard, ingesta ni despliegue. Mantener ambas mejoras anteriores.

## Decomposition

market_context_engine.py supera 400 líneas: agregar solo wrapper público sobre la consulta agregada existente; mantener serialización en market_context_evolution.py. No reestructurar el motor como parte de esta tarea.
