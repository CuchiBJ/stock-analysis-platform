## Context

El bloque "Sector Rotation" (`SectorHeatmap.tsx` consumiendo `/api/v1/sectors/performance`) renderiza hoy 11 tiles agrupados por `stocks.sector` (GICS Level 1). Para el operador momentum institucional, esa granularidad oculta rotaciones intra-sector que son justamente la señal accionable.

El universo activo tiene 2.480 stocks con `industry` populada (35% del total de 7.152). Las 155 industrias Yahoo presentes mapean naturalmente a ~25 grupos que la comunidad momentum/CANSLIM reconoce (Electronic Technology, Technology Services, Health Technology, Banks, Insurance, Defense, etc.).

Este cambio no introduce una nueva fuente de datos ni un nuevo cálculo — sólo re-categoriza los stocks existentes con resolución superior y refactoriza el `GROUP BY` del servicio.

## Goals / Non-Goals

**Goals:**
- Pasar de 11 a ~25 grupos visibles en el heatmap sin cambiar la lógica de cálculo de performance.
- Que el mapping viva en código versionado (`market_group_mapping.py`), no en DB — auditable via git, testeable, sin CRUD.
- Que el ingestor mantenga `market_group` actualizado automáticamente cuando llega un stock nuevo o se le actualiza el `industry`.
- Preservar la lectura visual macro: que se pueda ver "todo lo de tech está rojo" de un vistazo aunque sean 3 tiles separados, mediante un accent border de 2px por familia GICS padre.

**Non-Goals:**
- No introducir 197 IBD industry groups ni ranking 1-N. Los 25 grupos son resolución pragmática para Phase 1.
- No alterar el path del endpoint ni el shape del response — sólo cambia el contenido (más rows, distintos nombres en `name`).
- No tocar scoring, transition engine, regime engine, ni ninguna otra surface.
- No hacer drill-down al nivel de industry desde el heatmap.

## Decisions

### D1: Source of truth del mapping — código vs DB

**Decisión**: el mapping vive en `backend/app/services/market_group_mapping.py` como dict Python literal. La DB sólo guarda el resultado (`stocks.market_group`).

**Por qué**:
- Mapping = ~155 entries. Cabe en un archivo de ~200 LOC.
- Cambios al mapping = code review + git diff. Más auditable que una tabla CRUD-able.
- No requiere admin UI, ni endpoints de gestión, ni permisos. Cero superficie adicional.
- Re-mapping = correr el script. Idempotente.
- Test unitario trivial: `assert map_industry_to_market_group("Semiconductors", "Technology") == "Electronic Technology"`.

**Rechazada**: tabla `market_group_mappings(yahoo_industry, market_group)` con CRUD. Hace falta endpoint admin, validación, permisos, UI. Drift garantizado.

### D2: Cómo persistir y cuándo recalcular

**Decisión**: dos puntos de escritura.
1. **Script one-time `populate_market_group.py`**: para el backfill inicial sobre los 2.480 stocks con `industry IS NOT NULL`. Idempotente.
2. **Hook en `stock_ingestor.py`**: cada vez que se setea `stock.industry` o `stock.sector` (en `create`, `update`, `update_sector_industry`), se recalcula y persiste `market_group` en la misma transacción.

**Por qué dos puntos**: el script cubre el estado actual; el hook garantiza que no haya drift futuro. Si después se cambia el mapping (agregar una industria nueva, mover una), basta con re-correr el script para reconciliar.

**Alternativa rechazada**: trigger SQL. Acoplaría el mapping a Postgres y rompería el principio de "mapping vive en código".

### D3: Stocks sin `industry`

**Decisión**: `stocks.market_group` queda NULL. El `sector_service` filtra `WHERE s.market_group IS NOT NULL`. Esos 4.672 stocks no aparecen en el heatmap.

**Por qué**: el heatmap actual ya filtra implícitamente (un sector que no tiene stocks con datos no aparece). No hay regresión. Cuando el ingestor llene esos `industry` desde Yahoo, automáticamente entran al mapping vía D2.

**Alternativa rechazada**: bucket "Unclassified" con los 4.672 stocks. Sería un tile gigante sin valor de rotación — ruido puro.

### D4: Granularidad final del mapping — 25 grupos

**Decisión final**: 25 market groups, no 33 (IBD ortodoxo) ni 50 (Yahoo industries directos).

**Justificación de la elección**:
- 11 GICS = demasiado ancho (problema actual).
- 33 IBD = no podemos derivarlo de Yahoo industry sin pérdida; muchos de los 33 IBD requieren splits que Yahoo no provee (ej. IBD separa "Software-Enterprise" de "Software-SaaS"; Yahoo solo dice "Software-Application").
- 155 industrias Yahoo directas = grid imposible de leer (5 cols × 31 rows).
- **25 grupos** = sweet spot. Cada grupo tiene > 20 stocks (excepto Renewables = 22 y Auto = 32, que son operativamente relevantes igual). Grid 5×5 = 25 tiles, todo en una pantalla.

Grupos definidos en proposal.md sección "What Changes" con counts validados contra DB.

### D5: Distinción visual entre grupos del mismo sector padre

**Decisión**: cada tile lleva un borde izquierdo de 2px coloreado por familia GICS padre. Mantiene la lectura "macro" sin reintroducir GICS L1 como grupo.

```
Electronic Tech     ← borde izquierdo verde (Tech family)
Technology Svcs     ← borde izquierdo verde (Tech family)
Health Technology   ← borde izquierdo magenta (Healthcare family)
Banks               ← borde izquierdo azul (Financial family)
```

Tabla de colores propuesta:
- **Tech family** (Electronic Technology, Technology Services): `border-l-cyan-500`
- **Healthcare family** (Health Technology, Health Services): `border-l-pink-500`
- **Financial family** (Finance, Banks, Insurance): `border-l-blue-500`
- **Industrial family** (Defense, Industrials, Commercial Services, Transportation): `border-l-amber-500`
- **Consumer family** (Retail, Consumer Cyclical, Auto, Consumer Staples, Consumer Products): `border-l-orange-500`
- **Energy family** (Energy, Renewables): `border-l-red-500`
- **Materials family** (Mining & Metals, Chemicals, Building): `border-l-stone-500`
- **Yield family** (Real Estate, Utilities, Media & Telecom): `border-l-purple-500`

Aplicado mediante un map `MARKET_GROUP_TO_FAMILY` también en `market_group_mapping.py`.

### D6: Inclusión de cross-sector items en el mapping

**Decisión**: algunas industrias se mueven entre sectores GICS y su grupo natural:
- `Internet Content & Information` (Communication Services GICS) → **Technology Services** (la familia "tech" intuitiva)
- `Solar` (Technology GICS) → **Renewables** (que también incluye `Utilities - Renewable`)

**Por qué**: el operador busca rotación temática, no estricta GICS. "Solar" pertenece naturalmente con renovables aunque Yahoo lo clasifique como Technology. `Internet Content & Information` (Meta, Alphabet) tiene comportamiento más cercano a software que a media tradicional.

Documentado explícitamente en el mapping con comentarios `# cross-sector: was X in Yahoo, mapped to Y for momentum coherence`.

### D7: Shell Companies y otros valores no-operativos

**Decisión**: ciertas industrias Yahoo no entran al mapping (return `None`):
- `Shell Companies` (73 stocks) — SPACs, no son operating companies.

**Por qué**: incluirlos crearía un grupo sin valor de rotación. Quedan con `market_group = NULL` y se excluyen del heatmap. Si alguno se convierte en operating company, su `industry` cambia y el hook D2 los re-mapea.

### D8: Shape del API response — backward incompatible?

**Decisión**: el campo `name` del response ahora trae market group name. El field `stock_count` puede ser menor por grupo (los 11 sectores eran agregados grandes, los 25 grupos son menores). No hay otro cambio en el shape.

**Compatibilidad**: el único consumer es `SectorHeatmap.tsx`, que se actualiza en el mismo change. No hay terceros consumiendo este endpoint. Breaking change interno, sin breaking externo.

## Risks / Trade-offs

1. **Mapping puede ser cuestionado** (¿"Insurance Brokers" en Insurance vs Commercial Services?). Mitigación: el mapping vive en código, una decisión = un commit; siempre revisable.
2. **Performance del query**: añadir índice en `market_group` cubre los `WHERE` y `GROUP BY`. El JOIN sigue siendo `stocks → stock_metrics`. Sin regresión.
3. **Cobertura limitada al 35%** (2.480/7.152). Mitigación: el ingestor de Yahoo ya tiene `update_sector_industry_for_all`; correrlo lleva la cobertura a ~90%. Out of scope para este change pero recomendado como follow-up.
4. **25 tiles puede ser muchos para pantallas chicas**. Mitigación: el producto es desktop-only (`WHAT_THIS_PRODUCT_IS_NOT.md`). En desktop estándar (≥1366px) el grid 5×5 entra cómodo.
5. **Drift entre `sector` GICS y `market_group`**: ambos campos coexisten. `sector` queda para queries que necesiten GICS L1 (ninguna conocida hoy excepto este servicio que se refactoriza). Aceptable; `sector` no se borra.
6. **Cross-sector decisions (Solar, Internet Content) pueden confundir**: documentados en comentarios del mapping y en el guide (futuro). Riesgo bajo.
7. **El hook en `stock_ingestor` agrega trabajo en cada ingest**: una operación de dict lookup + un set de campo. Costo despreciable.
8. **Estética del accent border 2px**: puede chocar visualmente con el `colors.bg` actual de cada tile. A validar post-implementación; si compite, bajar a 1px o reservar el accent border solo para casos sin color (gris).
