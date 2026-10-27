## ADDED Requirements

### Requirement: Guided market context reading
La página SHALL organizar su contenido en una columna con cinco grupos ordenados: Lectura actual; Cambios y alertas; Índices y volatilidad; Participación y sectores; Evolución y continuidad. Cada grupo SHALL tener un título h2 reconocible y los subtítulos de sus componentes SHALL respetar la jerarquía. La postura y su síntesis SHALL seguir primero; deterioro y divergencias SHALL permanecer visibles antes de la evidencia extensa. Las métricas adicionales SHALL seguir disponibles al final.

Implementation: `frontend/components/market-context/MarketContextPage.tsx` y componentes directos.

#### Scenario: Complete context
- **WHEN** hay una respuesta de contexto disponible
- **THEN** se muestran los cinco grupos en ese orden, con postura inicial, cambios y divergencias, índices, participación/sectores y evolución/calidad, sin perder evidencia existente

#### Scenario: Loading or missing context
- **WHEN** el contexto está cargando, vacío o falló sin datos previos
- **THEN** se mantiene el estado correspondiente y no se muestran enlaces a secciones inexistentes

### Requirement: Accessible section index
La página SHALL exponer un índice horizontal con exactamente cinco enlaces a IDs únicos y estables de los grupos. SHALL admitir teclado, deep links por hash y navegación normal del navegador. SHALL indicar una sola sección activa mediante `aria-current="location"`, actualizada por navegación y desplazamiento. En escritorio el índice SHALL mantenerse visible al desplazar; destinos y foco SHALL quedar accesibles sin superponerse con el índice. En tablet los enlaces SHALL envolver sin overflow de página. Desmontar SHALL retirar observadores/listeners.

Implementation: `frontend/components/market-context/MarketContextPage.tsx`, componente local de índice y pruebas E2E.

#### Scenario: Navigate to a group
- **WHEN** se activa con teclado o click «Participación y sectores»
- **THEN** el hash apunta al grupo, su título queda visible y el enlace es el único marcado como actual

#### Scenario: Scroll and direct link
- **WHEN** se abre un enlace directo al último grupo o se desplaza manualmente hasta él
- **THEN** «Evolución y continuidad» es el enlace actual y no se modifica la sesión global ni se solicita otro contexto por navegar

### Requirement: Spanish presentation labels preserve original evidence
Descriptores visibles de participación, liderazgo, salud, densidad y continuidad SHALL presentarse en español mediante mapeos de presentación. Valores ausentes/desconocidos SHALL indicar falta de clasificación sin atribuir mejora o deterioro. Los códigos y valores de entrada SHALL permanecer intactos e inspeccionables en evidencia o auditoría; las decisiones, colores semánticos y datos de API SHALL conservar sus contratos.

Implementation: `frontend/lib/market-context-labels.ts`, `frontend/components/market-context/ContextEvidence.tsx` y pruebas unitarias.

#### Scenario: Known descriptors
- **WHEN** se recibe participación NARROWING, salud RECOVERING o liderazgo THINNING
- **THEN** la lectura utiliza etiquetas españolas con el mismo significado y conserva los códigos originales en evidencia inspeccionable

#### Scenario: Unknown descriptor
- **WHEN** llega un código no reconocido o falta el valor
- **THEN** se muestra un estado neutral de falta de clasificación y no se inventa su interpretación

### Requirement: Explicit temporal scope and transition hierarchy
Cada bloque SHALL explicitar su ventana o par de fechas real y preservar avisos de datos atrasados, faltantes o no comparables. Extremos diarios SHALL titularse «Extremos de la sesión», comparados con la rueda previa y distintos de los máximos de 52 semanas. El selector histórico SHALL llamarse «Inspeccionar sesión» y explicar que sólo cambia la inspección local. La variación del índice SHALL tener al menos igual prominencia tipográfica que su precio absoluto. La cotización demorada de VIX SHALL distinguirse de su cierre diario de respaldo sin atribuirle un cierre oficial.

Implementation: `MarketContextPage.tsx`, `SectorBreadth.tsx`, `MarketEvolution.tsx`, `SessionChanges.tsx`.

#### Scenario: Different observation windows
- **WHEN** conviven variaciones diarias, delta de cinco ruedas e historia de hasta veinte ruedas
- **THEN** cada ventana se identifica junto a su contenido y elegir una fecha histórica no cambia la postura ni la fecha de cabecera

#### Scenario: Missing or delayed evidence
- **WHEN** VIX falla, un benchmark no coincide con as_of o falta una observación histórica
- **THEN** se mantienen los avisos, cobertura y ausencia de comparación sin presentar datos faltantes como estables

### Requirement: Sector synthesis precedes detail without losing evidence
El resumen existente de actividad y concentración sectorial SHALL preceder a la tabla histórica. La lectura SHALL conservar tasas con sus denominadores, fechas, cobertura y estados sin eventos/sin cobertura diferenciados. SHALL mantenerse la selección de un único sector, su detalle fechado, metodología y auditorías. Las síntesis SHALL derivar exclusivamente de evidencia real mediante lógica determinista existente; la maqueta no SHALL aportar cifras, conclusiones fijas, nuevos scores ni recomendaciones.

Implementation: `frontend/components/market-context/SectorEvolution.tsx`, `SectorBreadth.tsx` y pruebas de render/E2E.

#### Scenario: Available sector history
- **WHEN** hay historia sectorial válida
- **THEN** la actividad y concentración aparecen antes de la tabla y seleccionar un sector abre sólo su detalle sin perder denominadores ni avisos

#### Scenario: Partial sector evidence
- **WHEN** no hay eventos, no hay cobertura o el servidor no ofrece historia sectorial
- **THEN** esos estados siguen diferenciados y el resto de contexto, índice y evidencia disponibles siguen funcionando
