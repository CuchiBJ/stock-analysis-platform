## Why

El gate `_is_quality_leader()` para `ENTERING_PULLBACK` confirma alineación de medias móviles **cortas** (`sma50 > sma150`) pero no confirma la **tendencia de largo plazo** (`sma150 > sma200`). Esto deja pasar stocks que están en una pull-up de corto plazo aunque la tendencia secular de 200 días aún sea negativa o lateral. La regla Minervini SEPA completa exige `sma50 > sma150 > sma200` (Stage 2 confirmado en los tres timeframes), no solo el par 50/150.

Esto viola Principio 9 (señal institucional primaria — la sponsorship secular se mide vía SMA200) y Principio 7 (interpretabilidad — el gate dice "líder Minervini" pero falta uno de los tres trends).

## What Changes

- **Agregar un nuevo gate a `_is_quality_leader()` en `backend/app/services/transition_engine.py`**: `sma150 > sma200`. Combinado con el gate existente `sma50 > sma150`, queda la cadena completa Stage 2 de Minervini: SMA50 > SMA150 > SMA200.
- **Validación post-cambio**: confirmar que el feed sigue surfaceando líderes legítimos y que el filtro elimina stocks con tendencia secular débil o invertida.

No hay cambios de schema, no hay recálculo de métricas, no hay cambios de API.

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities

- `transition-engine`: el Requirement "ENTERING_PULLBACK SHALL Detect Quality Leader Approaching EMA From Above" agrega un octavo quality gate a la lista de criterios SEPA.

## Non-goals

- No agregar columna `ema150` al schema (decisión documentada: el sistema usa SMAs para timeframes >= 50 días, igual que Minervini).
- No cambiar el filtro de proximidad/dirección a EMA9/EMA21.
- No tocar otros transitions (`RECLAIMING`, `CONTINUATION_HOLDING`, etc.).
- No agregar gates de leadership (RS), structure (pullback_quality_score) ni volume — esos no fueron parte del scope original definido por el usuario.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/services/transition_engine.py` | Agregar `m.sma200 is not None` a la guard de null-checks y `m.sma150 > m.sma200` al return de `_is_quality_leader()` |
| `openspec/changes/redefine-entering-pullback/specs/transition-engine/spec.md` | Spec delta agregando el octavo gate |

Sin migraciones, sin recálculo, sin cambios visuales en frontend (el feed simplemente filtra mejor).
