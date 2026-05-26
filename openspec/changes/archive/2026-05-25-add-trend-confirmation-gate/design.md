## Context

`_is_quality_leader()` en `transition_engine.py` aplica los 7 criterios SEPA estándar para clasificar un stock como candidato a `ENTERING_PULLBACK`. El gate de alineación de medias actual es:

```python
m.sma50 > m.sma150
```

Esto confirma que el stock está en una pull-up reciente (50 vs 150 días) pero **no confirma** que la tendencia secular larga sea alcista. Un stock en una recuperación de 6 meses puede tener `sma50 > sma150` mientras `sma150 < sma200` (la tendencia de 200 días todavía cae). Es una recuperación, no un líder en Stage 2 confirmado.

La regla SEPA completa de Minervini exige los tres trends apilados: `sma50 > sma150 > sma200`. Este change agrega el segundo eslabón.

## Goals / Non-Goals

**Goals:**
- Confirmar que el stock está en Stage 2 secular completo (no solo en una pull-up de 50d sobre 150d).
- Eliminar del feed `ENTERING_PULLBACK` stocks con tendencia secular débil que pasan los otros 7 gates.
- Mantener el spirit Minervini: criterio de calidad estructural, no operacional.

**Non-Goals:**
- No agregar EMA150 (no existe en el sistema; los timeframes >= 50 días usan SMA por convención Minervini).
- No tocar el filtro `sma50 > sma150` existente — se mantiene como gate independiente.
- No agregar gates extra (RS, pullback_quality, weekly_trend) — esos están fuera del scope que el usuario definió originalmente.

## Decisions

### Decisión 1: Agregar `sma150 > sma200` como gate independiente

Opciones consideradas:

**Opción A (elegida): agregar `sma150 > sma200` como condición AND adicional**
```python
m.sma50 > m.sma150 and
m.sma150 > m.sma200
```
- Pro: cadena Minervini explícita y leíble: SMA50 > SMA150 > SMA200
- Pro: cada gate puede fallar independientemente, debugging claro

**Opción B descartada: reemplazar el gate actual por `sma50 > sma200`**
- Más permisivo (salta el chequeo intermedio). No es lo que el usuario pidió.

**Opción C descartada: usar EMA200 como referencia**
- Ya tenemos `current_price > ema200` como gate separado. Doblarlo no aporta.

### Decisión 2: Null-guard para `sma200`

`sma200` puede ser NULL si el stock tiene menos de 200 días de historia. El guard actual no incluye `sma200`. Agregarlo previene `TypeError` en la comparación.

### Decisión 3: No agregar nuevo Requirement separado

El gate es parte del cluster existente "Quality leader gates". Se modifica el Requirement actual con un octavo bullet, no se crea uno nuevo. Mantiene el spec coherente.

## Risks / Trade-offs

**[Riesgo 1: Stocks que pasaban con tendencia secular ambigua dejan de pasar]**
→ Aceptado y deseado. Si `sma150 < sma200`, la tendencia larga no está confirmada — el stock no es un líder Stage 2 completo. El filtro es por diseño.

**[Riesgo 2: Stocks recién listados o con < 200 días de data no pasan]**
→ Aceptado. Sin 200 días no se puede confirmar Stage 2. No es candidato a setup de líder institucional.

**[Riesgo 3: El feed puede quedarse vacío en regímenes débiles]**
→ Aceptado. "Nada hoy" es válido (Principio 2: Scarcity is signal). Es preferible un feed vacío a uno lleno de pseudo-líderes.

## Migration Plan

1. Editar `_is_quality_leader()` en `transition_engine.py`: agregar `sma200 is not None` al guard y `sma150 > sma200` al return.
2. Editar el spec `redefine-entering-pullback/specs/transition-engine/spec.md` agregando el octavo gate en la tabla.
3. Verificar el feed `GET /api/v1/transitions/live?limit=20` post-cambio.
4. Inspeccionar 1-2 stocks que se hayan caído del feed para confirmar que es por `sma150 <= sma200`.

Rollback: revertir las 2-3 líneas en `_is_quality_leader()`.

## Open Questions

*(ninguna — el cambio es un único gate adicional, sin ambigüedades)*
