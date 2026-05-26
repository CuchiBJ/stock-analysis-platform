## Why

El bloque "Sector Rotation" actual agrupa los 7.152 stocks del universo por **GICS Level 1** (11 sectores: Technology, Healthcare, Financials, ...). Ese nivel es demasiado ancho para lecturas de rotación de capital institucional.

Ejemplo concreto: "Technology +2.3%" oculta que dentro hay 153 stocks de **Electronic Technology** (semiconductores, hardware) y 249 stocks de **Technology Services** (software, IT). Cuando semis lideran y software se queda atrás, GICS L1 da un único promedio que comprime la señal — perdiendo justamente lo que un trader momentum necesita ver. Lo mismo pasa en Healthcare (Biotech vs Healthcare Plans), Financials (Asset Managers vs Banks vs Insurance), Industrials (Defense vs Transportation vs Commercial Services).

El producto declara en PRODUCT_BRAIN que la rotación sectorial es señal de primer orden para momentum trading. Hoy esa señal se entrega con resolución insuficiente. Defiende **Principio 9 (Institutional sponsorship is primary signal)** — la rotación de capital institucional ocurre a nivel de industry group, no de sector L1.

## What Changes

- **Nuevo campo `stocks.market_group VARCHAR(50)`** con índice — agrupación tipo IBD/momentum-trading (~25 grupos vs los 11 GICS actuales).
- **Nuevo módulo `backend/app/services/market_group_mapping.py`** con un dict literal `YAHOO_INDUSTRY_TO_MARKET_GROUP` que mapea las 155 industrias Yahoo presentes en la DB → 25 market groups. Función pública `map_industry_to_market_group(industry: str | None, sector: str | None) -> str | None`.
- **Migración Alembic** `add_market_group_to_stocks` — agrega la columna nullable con índice.
- **Script `backend/scripts/populate_market_group.py`** — recorre `stocks WHERE industry IS NOT NULL`, aplica el mapping, hace bulk update. Idempotente (se puede re-correr).
- **Hook en `stock_ingestor.py`** — cuando se setea `industry` o `sector` desde Yahoo Finance, recalcular y persistir `market_group` en la misma transacción. Garantiza que stocks nuevos hereden el grupo sin necesidad de re-correr el script.
- **Refactor `sector_service.calculate_sector_performance`** — `GROUP BY s.sector` → `GROUP BY s.market_group`. Misma lógica de cálculo (avg perf_1w, perf_4w, RS vs SPY, RVOL, leaders). Filtra `market_group IS NOT NULL` (excluye Shell Companies y stocks sin mapping).
- **Renombrar endpoint mental**: `/api/v1/sectors/performance` sigue siendo el path (compat), pero la respuesta ahora retorna 25 market groups en lugar de 11 sectores. Field `name` del response trae el market group name (`"Electronic Technology"`, no `"Technology"`).
- **`SectorHeatmap.tsx`**: grid pasa de 4 a 5 columnas para alojar 25 tiles sin scroll. Cada tile mantiene formato actual (nombre, %, stock count, trend, strength).
- **Cards: prefix de color por sector padre** — para preservar lectura visual macro, cada tile tiene un borde izquierdo de 2px coloreado por familia GICS (verde-tech, magenta-health, azul-finance, etc.). Permite ver "todo tech está rojo" de un vistazo aunque sean 2-3 grupos.

## Capabilities

### New Capabilities
- `market-group-rotation`: clasifica el universo en ~25 grupos momentum-trading derivados de Yahoo `industry`, y expone performance agregada por grupo para lectura de rotación de capital con resolución superior a GICS L1.

### Modified Capabilities
- (none) — `universe-management` no se toca; el mapping es derivado, no canónico (la columna `industry` original se mantiene como source of truth).

## Impact

- **Nuevo**: `backend/app/services/market_group_mapping.py`, `backend/scripts/populate_market_group.py`, migración Alembic.
- **Modificado**: `backend/app/models/stock.py` (nueva columna), `backend/app/services/sector_service.py` (group by + filter), `backend/app/data/ingestors/stock_ingestor.py` (auto-populate en ingest), `frontend/components/charts/SectorHeatmap.tsx` (5 cols + accent border).
- **Sin cambio**: API path `/api/v1/sectors/performance`, shape del response (mismo schema, distintos valores en `name`), backend de scoring/transition/regime engines, otros surfaces.
- **DB**: una migración trivial agregando columna nullable + un script de populate one-time. Sin breaking changes.

## Non-goals

- **No usar IBD industry groups oficiales** (197 grupos rankeados). Eso requiere fuente de datos externa (FactSet, Finviz scraping) — no aborda este change. Los ~25 grupos son derivados de Yahoo `industry` con nombres alineados a la taxonomía IBD para reconocibilidad.
- **No incluir ranking 1-N tipo IBD** (Group Rank #3/197). Out of scope; el heatmap actual rankea por performance dentro del set visible — suficiente para esta iteración.
- **No tocar el scoring** (priority_score, continuation_prob, etc.). `market_group` solo se usa para el heatmap de rotación; no entra en cálculos de setup.
- **No re-mapear stocks con `industry IS NULL`** (4.672 stocks, 65% del universo). Quedan con `market_group = NULL` y se excluyen del heatmap. Cobertura del heatmap = ~2.480 stocks (igual que cobertura actual de `industry`). Mejora incremental cuando el ingestor llene los NULL via Yahoo.
- **No mostrar drill-down por industry** (click en "Electronic Technology" → lista de Semiconductors vs Hardware). Out of scope; la columna `industry` queda disponible para un futuro drawer.
- **No persistir el mapping en DB como tabla** (`market_group_mapping(yahoo_industry, market_group)`). El mapping es código (`market_group_mapping.py`) versionado con la app — más simple, audit-able via git diff, no necesita CRUD.
- **No mantener compatibilidad con consumers que esperen exactamente 11 GICS sectors**. El único consumer hoy es `SectorHeatmap.tsx`, que se actualiza en este mismo change.
