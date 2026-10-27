## Why

Market Context reúne evidencia útil, pero su lectura exige recorrer bloques sin orientación, interpretar estados internos en inglés y reconstruir ventanas temporales. Esta mejora aplica la visual revisada con el usuario para defender compresión de contexto, transiciones antes que snapshots, deterioro visible y claridad operativa.

## What Changes

- Organizar la página en cinco secciones: Lectura actual; Cambios y alertas; Índices y volatilidad; Participación y sectores; Evolución y continuidad.
- Añadir un índice horizontal por anclas, con sección activa, navegación por teclado y comportamiento fijo durante el desplazamiento en escritorio.
- Mostrar ventanas y fechas explícitas; diferenciar extremos diarios de máximos de 52 semanas y el selector histórico de la sesión global.
- Traducir los descriptores visibles de participación, liderazgo, salud, densidad y continuidad. Conservar los códigos originales en auditoría.
- Reutilizar las síntesis deterministas existentes, colocar resumen sectorial antes de su tabla y reducir el peso del precio absoluto frente a cambios y contexto.
- Preservar evidencia desplegable, avisos, cobertura, estados parciales y contratos de datos actuales.

## Capabilities

### New Capabilities

- `market-context-reading`: Recorrido guiado, navegación interna y presentación temporal y semántica de la página dedicada de contexto.

### Modified Capabilities

Ninguna especificación canónica existente cambia: `market-context-presentation` gobierna el drawer. Este cambio complementa las capacidades de la página ya implementadas y aún no archivadas.

## Non-goals

No cambiar política, umbrales, scoring, persistencia, endpoints, autenticación ni Dashboard/drawer. No copiar cifras o conclusiones ilustrativas de la maqueta. No generar predicciones, recomendaciones, nuevos indicadores, dependencias ni un rediseño global. No convertir cotizaciones demoradas de VIX en cierres ni eliminar advertencias para compactar.

## Impact

Sólo frontend: `frontend/components/market-context/`, un helper de etiquetas si es necesario y sus pruebas; pruebas de render/navegación aisladas con fixtures. Sin migración ni cambios backend. Se preservan todos los cambios preexistentes del worktree.

## Decision filter

7/8: mejora velocidad, compresión, carga cognitiva, detección de transiciones y deterioro, flujo discrecional y lectura institucional. No modifica directamente la calidad de los setups. Cumple los tres criterios obligatorios del filtro.
