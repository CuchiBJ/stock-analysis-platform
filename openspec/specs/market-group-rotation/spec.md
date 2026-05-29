# market-group-rotation Specification

## Purpose
TBD - created by archiving change introduce-market-group-rotation. Update Purpose after archive.
## Requirements
### Requirement: Market group taxonomy MUST live in versioned code

El sistema SHALL exponer una taxonomía de ~25 market groups (no GICS L1, no Yahoo industries directas) que clasifique los stocks por temática de rotación institucional. Esta taxonomía y su mapping desde Yahoo `industry` SHALL vivir en código versionado (`backend/app/services/market_group_mapping.py`), no en tablas DB CRUD-able. La columna `stocks.market_group` SHALL almacenar únicamente el resultado del mapping aplicado al valor actual de `industry` (o, como fallback, de `sector`).

Esto garantiza: (a) que cualquier cambio al mapping pase por code review y git history; (b) que el código de aplicación tenga el mapping en memoria sin lookup a DB; (c) que no se genere superficie administrativa (UI, endpoints, permisos) para mantener el mapping.

#### Scenario: Mapping function returns canonical group

- **WHEN** se invoca `map_industry_to_market_group(industry="Semiconductors", sector="Technology")`
- **THEN** retorna `"Electronic Technology"`

#### Scenario: Mapping function handles missing data

- **WHEN** se invoca `map_industry_to_market_group(industry=None, sector=None)`
- **THEN** retorna `None`

#### Scenario: Mapping excludes non-operating companies

- **WHEN** se invoca `map_industry_to_market_group(industry="Shell Companies", sector="Financial Services")`
- **THEN** retorna `None` (Shell Companies / SPACs no son operating companies y no entran al heatmap de rotación)

### Requirement: Stocks MUST receive market_group automatically on ingest

El componente `stock_ingestor.py` SHALL recalcular y persistir `stocks.market_group` en cada operación que modifique `stocks.industry` o `stocks.sector`. Esto garantiza que stocks nuevos heredan el grupo sin requerir una corrida manual del script de populate, y que actualizaciones de `industry` desde Yahoo Finance se reflejen automáticamente.

#### Scenario: Industry update triggers market_group recalculation

- **WHEN** el ingestor actualiza `stock.industry` de NULL a `"Biotechnology"` para un símbolo
- **THEN** en la misma transacción, `stock.market_group` queda seteado a `"Health Technology"`

#### Scenario: Industry change re-maps market_group

- **WHEN** un stock ya clasificado como `"Health Technology"` recibe un nuevo `industry = "Asset Management"` (caso raro: cambio de modelo de negocio)
- **THEN** `stock.market_group` se actualiza a `"Finance"` en la misma operación

### Requirement: Sector rotation endpoint MUST group by market_group

El endpoint `GET /api/v1/sectors/performance` SHALL agrupar los stocks por `market_group` (no por `sector` GICS L1). El cálculo de las métricas agregadas (`performance_weekly`, `performance_monthly`, `performance_vs_spy`, `trend`, `strength`, `volume_trend`, `stock_count`, `leaders`) sigue siendo idéntico — sólo cambia el predicado de agrupación. El endpoint SHALL filtrar `WHERE stocks.market_group IS NOT NULL` para excluir stocks sin clasificación (sin `industry` poblado, o industria no mapeada como Shell Companies).

El campo `name` del response trae el market group name (ej. `"Electronic Technology"`, `"Health Technology"`), no el sector GICS.

#### Scenario: Response shape unchanged

- **WHEN** un consumer llama `GET /api/v1/sectors/performance?timeframe=daily`
- **THEN** la respuesta es un array de objetos con los mismos fields que antes (`name`, `performance_weekly`, `performance_monthly`, `performance_vs_spy`, `trend`, `strength`, `volume_trend`, `stock_count`, `leaders`), pero con ~25 elementos en lugar de ~11, donde `name` contiene market group names

#### Scenario: Unclassified stocks excluded

- **WHEN** existen stocks con `market_group IS NULL` (por `industry IS NULL` o por estar en industrias no mapeadas)
- **THEN** esos stocks NO se cuentan en ningún tile del response (no hay tile "Unclassified")

### Requirement: Heatmap MUST visually distinguish market group families

El componente `SectorHeatmap.tsx` SHALL renderizar cada tile con un accent border (2px, lado izquierdo) coloreado por la familia GICS padre del market group (Tech, Healthcare, Financial, Industrial, Consumer, Energy, Materials, Yield). Esto preserva la lectura macro ("toda la familia tech está en rojo") sin reintroducir GICS L1 como agrupador.

El grid SHALL ser de 5 columnas para alojar 25 tiles sin scroll vertical excesivo en pantallas desktop (≥1366px).

#### Scenario: Tech family tiles share accent color

- **WHEN** el operador ve el heatmap y los tiles "Electronic Technology" y "Technology Services" están presentes
- **THEN** ambos tiles tienen el mismo accent border color (e.g. cyan), indicando que pertenecen a la familia tech, aunque sus `colors.bg` (verde/rojo según performance) sean independientes

#### Scenario: Grid layout for 25 tiles

- **WHEN** el response trae 25 market groups
- **THEN** el grid se renderiza en 5 columnas × 5 filas, sin scroll horizontal y con scroll vertical mínimo

