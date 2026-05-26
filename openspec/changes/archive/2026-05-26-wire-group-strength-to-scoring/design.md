## Context

El change `introduce-market-group-rotation` (shipped 2026-05-25) agregó la columna `stocks.market_group` y el endpoint `/api/v1/sectors/performance` ahora devuelve ~24 grupos con `performance_monthly`. El operador ve la rotación en el heatmap.

El change `market-context-decision-wiring` (shipped 2026-05-24) estableció el patrón arquitectónico:
- Un módulo `context_decision_filter.py` que retorna un value object (`ContextMultiplier`).
- Aplicación del multiplier en endpoints (`/actionable`, `/queue/*`), no dentro del engine.
- Cache in-memory 5 min TTL, escape hatch (UNKNOWN → neutral) para cold-start.
- Composición multiplicativa con otros factores (regime_cont_mult).

Esta change replica ese patrón a nivel grupo. La estructura, el lifecycle y los puntos de integración son deliberadamente análogos para reducir carga cognitiva al leer el codebase.

**Universo actual** (verificado en DB, 2026-05-25): 24 grupos activos con stocks que pasan el quality filter (`avg_volume_10d >= 500k`, `current_price >= 5.0`, `adr_percent >= 2.0`). Counts van desde 19 (Renewables) hasta 262 (Health Technology). Top-3 monthly y bottom-3 monthly cambian día a día — el operador necesita lectura actualizada.

## Goals / Non-Goals

**Goals:**
- Que el ranking de `/actionable` refleje la fuerza relativa del grupo del stock, sin que la lectura sea opaca al operador (badge visible siempre que el multiplier no sea 1.0).
- Que el operador navegando queue lenses vea, en cada fila, si el candidato vive en un grupo top/bottom — sin que el sistema le altere el orden propio de la lens.
- Reusar la infraestructura de `context_decision_filter` (cache, value object, composición multiplicativa) para no introducir un patrón nuevo cuando uno ya funciona.
- Que sea reversible: desactivar el multiplier es un `if` en el endpoint; revertir el badge es bajar prop a `null`.

**Non-Goals:**
- Suppression dura de setups por grupo (rule a nivel grupo no aplica: la rotación de grupos es ruidosa intra-día, contexto macro es estructural).
- Cambiar el sort key de queue lenses (cada una tiene tesis distinta: U&R por event_age, emerging por perf_13w, building-bases por atr_range).
- Persistir el group_strength por stock o por timestamp. Es derivado y recalculable.
- Multiplier por símbolo dependiente de su RS *vs su grupo* (relative strength intra-group). Phase 2 si emerge necesidad.
- Cambios al `setup_priority_engine` (sigue siendo puro por-símbolo).

## Decisions

### D1: Métrica de fuerza — percentil de `performance_monthly`

**Decisión**: Rankear los ~24 grupos por `performance_monthly` (campo ya en el response de `sector_service`). Top 20% (5 grupos) → `leader`/1.15. Bottom 20% (5 grupos) → `weak`/0.85. Resto (~15 grupos) → `neutral`/1.00.

**Por qué**:
- `performance_monthly` ya está computado y cacheado por `SectorService.calculate_sector_performance` (con `@cache_sectors`). Reuso completo.
- Mensual filtra ruido intra-día y intra-semana — un grupo que rebotó hoy desde un mes en rojo no se convierte en "leader" hasta que el mes acompañe.
- Percentil es robusto a outliers y siempre genera distribución (no depende de thresholds absolutos que dependen del régimen).
- Top/bottom 20% son 5 grupos cada bucket → suficientemente selectivo sin ser draconiano.

**Rechazada**: `performance_vs_spy` (binaria implícita, pierde matiz en mercados planos); `trend` field del response (acceleración puede ser rebote técnico no liderazgo); combinación multi-factor (complejidad sin valor probado en Phase 1).

### D2: Rango del multiplier — suave (0.85 – 1.15)

**Decisión**: Multiplier en {0.85, 1.00, 1.15} (3 buckets).

**Por qué**:
- Mueve el ranking sin aniquilar setups. Un setup técnicamente excelente en grupo débil baja ~15 puntos, pero sigue visible si su score base era alto.
- Suaviza el riesgo de over-rotación hacia hot groups cerca del techo (el grupo top tendría que estar muy claramente mal para que un boost del 15% sea regret material).
- Composición con `ctx_multiplier` (rango 0.5–1.1) garantiza que macro siempre domine en regímenes adversos: `0.85 × 0.5 = 0.425` vs `1.15 × 0.5 = 0.575` — incluso el grupo top no salva un setup en mercado COLLAPSING.
- Tres buckets discretos en lugar de función continua: explicable al operador en una frase ("top 5 grupos del mes ganan boost del 15%"), debugeable sin abrir un notebook.

**Rechazada**:
- Rango medio (0.75–1.25): boost demasiado opinionado para Phase 1 sin recalibración empírica.
- Rango agresivo (0.5–1.3): efectivamente filtra setups; rompe el principio de "operador decide, sistema asiste".
- Función continua basada en z-score: complejidad sin valor; los 3 buckets capturan 95% del valor.

### D3: Composición con `ctx_multiplier` — multiplicativa, en este orden

**Decisión**: `final_score = clamp_100(priority_score × ctx_multiplier × group_multiplier)`.

**Por qué**:
- Multiplicación es asociativa y conmutativa: el orden no importa matemáticamente. Pero la convención de leerlo `score × macro × grupo` refleja jerarquía: macro pesa más (rango más amplio), grupo modula.
- Composición pura, sin lógica condicional. Cualquier desarrollador puede leer una línea y entender.
- El clamp a 100 después de las dos multiplicaciones evita que un setup pase de 100 (que rompe la semántica de "score 0–100").

**Rechazada**: aditiva (`+ delta`) — perdería la propiedad de que macro domina; replacement (`if grupo fuerte: ignorar ctx`) — viola separación de concerns.

### D4: Dónde se aplica — solo `/actionable` mueve ranking; queue solo decora

**Decisión**:
- `/actionable` (transitions): multiplier aplicado al `priority_score` (igual que ctx_multiplier), badge en response.
- `/queue/u-and-r`, `/queue/emerging-leaders`, `/queue/building-bases`: solo badge en cada item del response. Sort key intacto.

**Por qué**:
- `/actionable` compara setups heterogéneos (distintos states, distintos setup_types) usando `priority_score` como denominador común. Ahí, ajustar el score por grupo es legítimo — está comparando manzanas con manzanas + contexto.
- Cada queue lens responde a una tesis distinta:
  - U&R ordena por "reciencia del evento" (event_age) → la fuerza del grupo es ortogonal a "cuán reciente fue el pre-reclaim".
  - Emerging-leaders ordena por "fuerza individual" (perf_13w) → ya está midiendo fuerza absoluta del símbolo.
  - Building-bases ordena por "tightness de la base" (atr_range) → estructural, multi-semanal, no rotacional.
- Meter group_mult en esos sorts ensucia tesis con una métrica ortogonal. Por eso queda solo como badge informativo.

**Rechazada**: aplicar multiplier también en queue (ensucia sort logic, decisión por-lens compleja, building-bases no debería verse afectado).

### D5: Edge cases — `market_group IS NULL` y grupos chicos

**Decisión**:
- `market_group IS NULL` (Shell Companies, stocks sin industry mapeado) → `(multiplier=1.0, badge="neutral")`. Mismo principio que UNKNOWN macro en `context_decision_filter`: nunca penalizar por dato faltante.
- Grupo con menos de 5 stocks post-quality-filter → forzar `1.0/neutral`, aunque su `performance_monthly` lo ubique en top o bottom 20%. Razón: la varianza de una muestra de 4 stocks es demasiado alta para asignar un boost confiable. (Renewables=19, Insurance=32 post-filter no son problema; el guard es defensivo para grupos que post-quality queden chicos.)

**Por qué**: cold-start safety + robustez a noise. Espejo del decision filter macro.

### D6: Cache strategy — TTL 5 min, in-memory, por proceso

**Decisión**: Cachear el dict `{group: performance_monthly}` por 5 min en memoria del proceso, idéntico a `context_decision_filter`. Cache key: `"current_group_strengths"` (singleton, no por-grupo).

**Por qué**:
- `SectorService.calculate_sector_performance` ya tiene `@cache_sectors`. Reusamos el cache existente: nuestro fetch llama al service y lee del cache si está caliente.
- Performance del query es O(stocks × 1 join + groupby Python), ya optimizado en sector_service.
- TTL 5 min porque el percentil de grupos cambia en escala de minutos (intra-day), no segundos.

### D7: Frontend — badge en CompactSetupCard, mismo componente en queue rows

**Decisión**: Crear un componente compartido `<GroupStrengthBadge group={...} badge={...} rank={...} />` en `frontend/components/shared/`. Usar en CompactSetupCard, TopActionableSetups, y filas de queue (u-and-r, emerging-leaders, building-bases pages).

**Por qué**: consistencia visual + un solo lugar para iterar el diseño. Si mañana cambiamos de emoji a icono Lucide, se cambia en un solo file.

**Diseño visual tentativo** (validar en implementación):
- `badge === "leader"`: chip cyan-400, texto "🔥 Group leader", tooltip "Electronic Technology · #2 of 25"
- `badge === "weak"`: chip amber-400, texto "⚠️ Weak group", tooltip "Consumer Staples · #23 of 25"
- `badge === "neutral"`: render `null` (no badge, no ocupa espacio)

### D8: Response shape changes — backward compatible

**Decisión**: Agregar campo `group_strength` (object) a cada item:
- `/actionable`: `{group: str, badge: str, multiplier: float}`
- `/queue/*`: `{group: str, badge: str}` (sin multiplier — no aplica)

**Compatibilidad**: campo nuevo, consumers viejos lo ignoran. El campo principal (`priority_score` en actionable) ya incluye el multiplier aplicado — el consumer ve el score final ajustado, igual que con `ctx_multiplier` hoy. Sin breaking change externo.

## Risks / Trade-offs

1. **Over-rotación hacia hot groups cerca del techo del grupo** → Mitigación: métrica mensual filtra ruido; multiplier suave (max 1.15) limita regret; badge visible obliga a confrontar la lectura (operador puede juzgar "este grupo ya corrió mucho").
2. **Double-counting con `rs_stability` del priority_score** → `relative_strength_spy` mide stock vs SPY; `group_strength` mide GRUPO vs otros grupos. Ortogonales conceptualmente. Un stock puede tener RS alto en grupo débil (líder relativo) — lo penalizamos ligeramente, lo cual es correcto en filosofía momentum (lider en grupo lateral ≠ lider en grupo top).
3. **Frontera dura del percentil (rank 5 vs rank 6) crea cliff de 15 puntos** → Aceptable Phase 1; granularidad de 3 buckets es opinada. Recalibración Aug 2026 puede mover a 5 buckets si el cliff genera regret observable.
4. **Grupos chicos (n<5 post-filter) ruido** → Mitigado por D5: forzar neutral.
5. **Mapping de market_group desactualizado** → Out of scope acá; responsabilidad de `market-group-rotation`. Si un stock tiene `market_group=NULL` por mapping nuevo no aplicado, cae a neutral (safe default).
6. **Cache stale de 5 min puede subir/bajar un setup justo cuando el rank cambia** → Aceptable: el operador no actúa en granularidad sub-5min sobre cambios de ranking de grupo. Si fuera crítico, invalidar cache cuando llega nuevo dato de precios resolvería — out of scope.
7. **Operador deja de mirar el heatmap porque "el badge ya me lo dice"** → Mitigación: tooltip del badge muestra "Electronic Technology · #2/25", lo cual invita al heatmap para ver contexto completo. Y la rotación de familias (cyan tech, pink healthcare) solo es legible en el heatmap.
8. **El multiplier puede empujar un setup mediocre arriba si su grupo está fuerte** → Aceptable: 80 × 1.15 = 92 (sube en ranking pero sigue siendo "calidad 80"). El número en pantalla refleja la composición; el operador ve qué pasó.

## Migration Plan

1. Crear módulo y tests (ningún impacto en endpoints existentes).
2. Integrar en `/actionable` con feature flag implícito: si `fetch_current_group_strengths` falla, multiplier = 1.0 universal (cold-start safety).
3. Integrar badge en CompactSetupCard, validar visualmente en `/dashboard`.
4. Integrar en `/queue/*` (cambio aditivo en response).
5. Integrar badge en queue pages.
6. Rollback: si el comportamiento es indeseable, comentar la línea `× group_multiplier` en transitions.py y bajar la prop `groupStrength` a `null`. Reversible en ~5 minutos.

## Open Questions

1. **¿Mostrar el rank numérico ("#2/25") o solo "leader/weak"?** — Recomendación: rank en tooltip, no en chip principal (mantener chip compacto). Validar en implementación.
2. **¿Color del chip "weak" debería ser red en lugar de amber?** — Amber sugiere "atención", red sugiere "no". Para Phase 1 (sin suppression), amber comunica mejor "es información, no orden".
3. **¿Aplicar en `setup_priority_engine.calculate_priority_score` también, para que la dataclass `SetupPriority` ya venga ajustada?** — No, mantener el engine puro (igual que con ctx_multiplier). Multiplier vive en el endpoint.
