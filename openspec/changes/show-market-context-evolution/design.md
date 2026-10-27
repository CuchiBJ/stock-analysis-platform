## Context

Engine._history entrega 10 puntos y convierte amplitud nula a cero. No sirve como fuente fiel para esta evolución. _daily_dimension_series ya entrega hasta n sesiones ordenadas con universe, breadth_ratio y leader_count en consultas agrupadas; se reutiliza, sin alterar cálculos. health.series contiene severidad fechada, no postura histórica.

## Goals / Non-Goals

**Goals:** Ver cambios y daño alineados temporalmente, inspeccionar sesión con teclado y mostrar huecos reales.
**Non-Goals:** Recalcular postura, inferir densidad o tendencia, modificar Dashboard, fuentes, migraciones o desplegar.

## Decisions

- Agregar método público engine.evolution_history(as_of) que solicita _daily_dimension_series(as_of,20) y delega serialización a nuevo market_context_evolution.py. Endpoint /overview reutiliza la instancia engine de analyze y añade evolution:[{date,breadth_ratio,leader_count}]. /current, _history y health permanecen idénticos. Endpoint ejecuta llamadas secuencialmente sobre misma sesión. Sin nuevo caché persistente; usa caché por instancia ya existente.
- Serializador toma máximo20 fechas <=as_of ordenadas; sin universe positivo devuelve ambas métricas null. Amplitud válida finita 0..1; cantidad válida entera >=0. Cero real con universo positivo se conserva. No mutar filas originales. Test wrapper que pide20, mapeo de nulos y endpoint aditivo; preservar prueba /current.
- Frontend tipo evolution opcional en MarketOverview para compatibilidad. Nuevo helper puro market-context-evolution.ts y componente MarketEvolution.tsx, insertado después de índices y antes de participación/sectores. No editar componentes previos de postura ni Dashboard. Sin fallback a history legacy porque contiene ceros artificiales: respuesta antigua sin evolution => «Evolución no disponible».
- Eje de fechas usa exclusivamente evolution con fecha ISO válida <=context.as_of, ordenado y recortado20; conserva fechas incluso si ambos valores nulos. Duplicados con valores conflictivos convierten la métrica en null; idénticos colapsan. No inventar fechas calendario. Severidad se une por fecha exacta desde health.series, sin inferir desde damaged boolean; ausencia es unknown. Si severidades duplicadas conflictivas, unknown. Validar valores en frontend también.
- Título «Evolución reciente · hasta 20 ruedas». Mostrar rango y cobertura por serie (ej. Amplitud10/20, Líderes20/20, Daño18/20) y advertencia si última fecha anterior a as_of. Si menos20, decir cuántas sesiones disponibles. Con eje vacío mostrar vacío sin charts. No afirmar recuperación confirmada ni predecir.
- Dos gráficas SVG de línea sin relleno, alineadas y apiladas, y banda de severidad sobre el mismo eje. Amplitud etiqueta «Sobre EMA21 (%)», escala fija0..100. Liderazgo etiqueta «Cantidad de líderes», escala0..max(1,max observado) indicada; jamás densidad%. Puntos aislados visibles; línea solo entre observaciones adyacentes del eje con valores válidos (huecos rompen trazo). Fechas inicial/final legibles. No comparar pendientes entre escalas distintas; mostrar nota escalas independientes.
- Daño: clean gris sólido, mild ámbar, severe rojo, unknown sin relleno/borde discontinuo; leyenda textual distingue sin daño clasificado de sin datos. SVG accesible con título/aria-label y alternativa textual de sesión; no depender solo del color/hover.
- Selector nativo «Sesión» lista todas las fechas, última seleccionada por defecto; muestra fecha, amplitud%, líderes cantidad, severidad texto. Cambiar selector actualiza esos valores y marcador vertical en ambas gráficas; no modifica datos ni hace requests. Si nueva respuesta pierde fecha seleccionada, usar última disponible de forma segura. Fecha no cambia de zona horaria.
- SVG responsive, tamaño compacto, sin librerías nuevas. Clases Tailwind literales en componente (lib no está en content). Pruebas helpers+render estático y QA navegador sintético de selección.

## Risks / Trade-offs

- Nueva consulta agrupada si analyze retorna caché → coste acotado a20 sesiones, sin consultas por cada día ni operaciones de escritura.
- Conteo de líderes no normalizado por universo histórico → etiqueta cantidad explícita y nota; no presentar como densidad ni fuerza relativa.
- Fechas obtenidas son sesiones disponibles del calendario interno → cobertura explícita; no prometer calendario bursátil completo.
- Backend engine extenso → wrapper mínimo y serializador aislado; no refactor general.

## Migration Plan

Sin migraciones; /overview aditivo y frontend compatible con respuesta previa. Validación local únicamente.

## Open Questions

Ninguna para este incremento.
