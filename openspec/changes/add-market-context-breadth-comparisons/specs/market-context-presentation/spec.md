## MODIFIED Requirements

### Requirement: Market context drawer MUST surface at most eight elements by default

El componente `MarketContextDrawer` SHALL presentar por defecto el contenido operacional resumido, incluyendo las métricas primarias existentes y tres comparaciones compactas de amplitud en Participation: nuevos máximos/mínimos de 52 semanas, avances/descensos desde la apertura y movimientos de al menos ±4%. El límite histórico de ocho elementos informacionales queda reemplazado por este conjunto explícito, los conteos y cobertura asociados, y el footer; no se añadirán otras filas raw por defecto. El ratio existente `highs_lows_ratio` SHALL explicarse como la proporción entre acciones cerca de máximos de 52 semanas y acciones alejadas de esos máximos, no como conteo de nuevos extremos ni proximidad a mínimos.

Las restantes métricas raw SHALL exponerse mediante un toggle colapsado por defecto, sin requerir un nuevo fetch. Las nuevas filas SHALL mostrar sus etiquetas completas en móvil, una barra con porcentaje positivo / eventos positivos y negativos, sus conteos, cobertura elegible/excluida y fecha efectiva. SHALL usar texto además de color. Una proporción nula SHALL presentarse como “Sin datos” cuando no haya cobertura y como “Sin eventos” cuando sí haya cobertura pero no eventos.

#### Scenario: Default render shows operational participation plus three breadth comparisons
- **WHEN** el operador abre el drawer con datos completos del backend
- **THEN** se muestran las métricas primarias existentes, las tres comparaciones con fecha, conteos y cobertura, los section headers y el footer, mientras las métricas raw permanecen colapsadas

#### Scenario: Ratio explanation distinguishes proximity from new extremes
- **WHEN** el operador consulta la fila `highs_lows_ratio`
- **THEN** la ayuda accesible aclara que el ratio contrasta acciones cerca y lejos de máximos de 52 semanas y que nuevos extremos se cuentan en la comparación separada

#### Scenario: Breadth zero-event and missing-coverage states
- **WHEN** una comparación no tiene eventos o no tiene símbolos elegibles
- **THEN** la fila muestra “Sin eventos” o “Sin datos” respectivamente y no presenta una barra o porcentaje de 50% fabricado

#### Scenario: Legacy endpoint payload
- **WHEN** se monta el drawer con una respuesta anterior que no contiene `breadth_comparisons`
- **THEN** el panel continúa renderizando el contenido anterior sin errores

#### Scenario: Raw metrics toggle and drawer remount
- **WHEN** el operador abre el toggle de métricas raw o cierra y vuelve a abrir el drawer
- **THEN** las métricas raw se muestran sin un fetch adicional y el toggle vuelve a quedar cerrado tras el remount

### Requirement: Phase 2-4 pending engines MUST render as a single line

El componente SHALL representar la lista `ctx.engines_pending` (típicamente: persistence, forgiveness, rotation, volatility, follow-through) como una sola línea de texto compacta de baja prominencia visual, no como cards individuales por engine.

#### Scenario: Pending engines line render
- **WHEN** `ctx.engines_pending` contiene N nombres de engines pendientes
- **THEN** se renderiza una sola línea compacta con los nombres separados por puntos medios, sin cards ni badges individuales
