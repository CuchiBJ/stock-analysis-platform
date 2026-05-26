## Why

`ENTERING_PULLBACK` es la señal más importante del live feed — el screener principal para detectar líderes institucionales en zona de entrada para swing trading. La implementación actual la dispara cuando el stock **ya cruzó por debajo** de la EMA21, sin ningún filtro de calidad. Esto produce falsos positivos (stocks que no son líderes, stocks reclamando desde abajo, stocks que ya rebotaron) y pierde el momento operacional real: el instante en que un líder de calidad **se acerca** a su EMA9 o EMA21 desde arriba, antes del cruce. Viola Principio 9 (señal institucional primaria) y Principio 7 (interpretabilidad — el feed muestra setups no accionables).

## What Changes

- **Redefinición semántica de `ENTERING_PULLBACK`**: deja de ser "stock cruzó EMA21 hacia abajo" y pasa a ser "líder de calidad acercándose a EMA9 o EMA21 desde arriba con distancia decreciente"
- **7 quality gates Minervini SEPA**: todos deben cumplirse antes de evaluar proximidad. Eliminan stocks que no son líderes institucionales
- **Filtro de proximidad ATR-normalizado**: EMA9 ≤ 0.5 ATR encima, EMA21 ≤ 1.0 ATR encima
- **Filtro de dirección**: la distancia a la EMA debe estar disminuyendo vs el día anterior — elimina rebotes y reclaims
- **Narrativa específica por EMA**: el feed distingue entre "testing EMA9" (entrada agresiva) y "testing EMA21" (entrada clásica swing)

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `transition-engine`: el Requirement "ENTERING_PULLBACK SHALL Detect Quality Leader Approaching EMA" reemplaza la detección actual de cruce simple

## Non-goals

- No modificar ningún otro tipo de transición (VOLUME_DRY_UP, COMPRESSING, WEAKENING, etc.)
- No agregar columnas nuevas a `stock_metrics`
- No cambiar el schema de respuesta del endpoint `/transitions/live`
- No aplicar los quality gates Minervini a otros transitions
- No tocar la lógica de scoring ni el priority engine

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/services/transition_engine.py` | Modificar `_determine_operational_transition()` y `_generate_operational_narrative()` |

Sin cambios de schema, sin migraciones, sin nuevos endpoints.
