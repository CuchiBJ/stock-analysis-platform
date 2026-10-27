## Why
La cabecera extensa y los doce gráficos sectoriales dificultan llegar al cambio relevante del día. El resumen tampoco puede comparar la postura porque no conserva las decisiones realmente emitidas. Este cambio reduce carga cognitiva y hace inspectables las transiciones sin reconstruir decisiones históricas con reglas actuales.

## What Changes
- Cabecera con postura, instrucción, síntesis, daño actual y continuidad; detalles de nivel/dirección/memoria y reparación bajo disclosure.
- Resumen compacto de evolución sectorial con tasas actuales, cambios en pp, cobertura y un sector seleccionado con su historial.
- Registro durable de la última postura observada por sesión, capturada al servir current/overview; comparación en el resumen cuando existen ambas sesiones exactas.

## Capabilities
### New Capabilities
- `market-context-compact-presentation`: Jerarquía compacta y detalle accesible de postura/sectores en la página dedicada.
- `market-context-posture-records`: Persistencia y comparación de posturas emitidas con fechas y evidencia.
### Modified Capabilities
Ninguna en specs canónicos; este incremento refina los cambios activos explain-market-context-posture, show-market-context-sector-evolution y summarize-market-context-session-changes.

## Impact
Frontend de la página dedicada y helpers/tests; endpoint backend, modelo/servicio/repositorio nuevos y migración aditiva. Sin dependencias nuevas ni cambios de política. El motor y scheduler grandes permanecen sin cambios; la persistencia se extrae a módulos acotados.

## Non-goals
No modificar Dashboard, algoritmo de postura, QQQ, extremos de sesión anterior ni ingesta. No aplicar migraciones, desplegar ni reconstruir posturas previas. No prometer captura de sesiones nunca consultadas.
