## Context

La página ya tiene síntesis de postura, cambios ordenados por deterioro, divergencias y disclosures de evidencia. Los cambios previos de Market Context figuran completos, pero sus archivos están sin commit; este trabajo parte de ese contenido y no lo reemplaza. La maqueta aprobada es referencia de composición, no fuente de datos. `frontend/package.json` usa Next 16/React 19; la mención a Next 14 en el contexto CLI está desactualizada.

## Goals / Non-Goals

**Goals:** orientar el escaneo, distinguir estado/cambio/evidencia, aclarar fechas y vocabulario, preservar trazabilidad y deterioro visible.

**Non-Goals:** alterar decisiones del motor o servicios; traducir valores de API; cambiar el drawer o layout global; introducir narrativas no soportadas ni fijar cifras de la maqueta.

## Decisions

1. **Cinco grupos en una columna.** `MarketContextPage` compone Lectura actual (PostureExplanation), Cambios y alertas (SessionChanges y MarketDivergences), Índices y volatilidad, Participación y sectores (participación, comparaciones, SectorBreadth y SectorEvolution) y Evolución y continuidad (MarketEvolution y calidad). Metodología adicional al final. Encabezados de grupo h2 y subencabezados h3, tamaños y espaciado consistentes. No sidebar ni pestañas que oculten secciones completas.
2. **Índice como navegación nativa.** Componente local con cinco enlaces a IDs estables, visible sólo con contexto disponible. Sticky en escritorio, fondo opaco y `scroll-margin-top` en destinos; tablet permite envolver enlaces. Una única sección activa mediante `aria-current="location"`, activación inicial/deep link/click y actualización por scroll, cleanup de listeners/observer. Teclado y hash funcionan sin depender de animación. La selección histórica no cambia el hash ni la sesión del contexto. Preferir cálculo/observación sencillo y probado; evitar dependencias.
3. **Lenguaje de presentación.** Helper dedicado en `frontend/lib/market-context-labels.ts`, por familia de descriptor (participación/liderazgo, salud, densidad, continuidad). Etiquetas de valores desconocidos explícitas y neutrales; el código original sigue en la respuesta/auditoría. Reutilizar colores semánticos, no colorear estados desconocidos como positivos. No cambiar el helper de política de postura para embellecer conclusiones.
4. **Tiempo y jerarquía.** Fecha `as_of` y universo se mantienen en cabecera; cada bloque conserva su período real, sin afirmar que todo sea cierre oficial. `SectorBreadth`: «Extremos de la sesión», «respecto de la rueda previa», fecha y explicación breve de que no son máximos de 52 semanas. Selector de MarketEvolution: «Inspeccionar sesión», alcance local visible. Precio absoluto más discreto que variación; fechas y advertencias no pierden prominencia. VIX conserva spot demorado/cierre de respaldo según la lógica existente.
5. **Síntesis antes de detalle.** Conservar explicaciones deterministas actuales y orden de deterioros. Adelantar síntesis de actividad y concentración de SectorEvolution a la tabla, sin duplicarla ni alterar tasas/denominadores. Mantener una selección de sector por vez, gráficos de escala fija, cobertura, metodología y auditorías. No crear un score ni conclusión agregada nueva sin evidencia.
6. **Verificación y preservación.** Pruebas unitarias del mapeo y render semántico; adaptar el E2E existente para cinco destinos, scroll/hash/teclado, períodos y evidencia plegada. Fixtures locales cubren VIX fallido/legacy/ausencia de comparación sin producción. Revisar diff contra una copia previa de archivos sin seguimiento, además del diff Git. Luna implementa; el agente principal integra y verifica.

## Risks / Trade-offs

- Índice envuelto puede tapar un destino → margen suficiente y QA de escritorio/tablet, sin altura fija.
- Duplicar h2 entre grupos y componentes → revisar jerarquía semántica completa y enlaces a IDs únicos.
- Compactar puede ocultar deterioro o ausencia de datos → avisos y daño actual permanecen visibles, sólo evidencia extensa colapsa.
- Cambiar orden rompe selectores E2E → actualizar expectativas de comportamiento, conservando regresiones de autenticación, fechas y estados parciales.
- Traducir códigos desconocidos inventaría significado → fallback neutral y original inspeccionable.

## Migration Plan

Sin migraciones ni dependencia nueva. Cambio frontend compatible con las respuestas existentes; rollback de los archivos tocados por este cambio sin revertir trabajo previo. No despliegue incluido.

## Open Questions

Ninguna bloqueante. La maqueta usa un ejemplo narrativo; la implementación usa los helpers y datos reales existentes.
