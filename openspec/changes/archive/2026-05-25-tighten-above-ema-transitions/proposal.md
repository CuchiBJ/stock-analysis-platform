## Why

`CONTINUATION_HOLDING` y `STABILIZING` son dos transition types que representan stocks **arriba de EMA21**, pero su lógica actual no aplica los quality gates que sí exige `ENTERING_PULLBACK` (recién auditado). Resultado: aparecen como "líderes en continuación" stocks que no son institucionales (NVDA con perf_1y=22%, AMN con sma_sep=0%, NN/MEI/AAON con sma_sep<5%), violando Principio 9 (institutional sponsorship es señal primaria).

Auditoría concreta del feed actual:
- **CONTINUATION_HOLDING**: solo chequea `0 ≤ distance_to_ema21_atr ≤ 1.5`. No requiere quality_leader, no chequea dirección, no chequea EMA9. AMN aparece como "continuation" aunque rompió EMA9 (d9=-0.52) y cayó 3% en un día.
- **STABILIZING**: chequea `|rs_change| < 1 AND |vol_change_pct| < 15`. Nadie aparece. Es un fallback genérico antes de STABLE. El nombre sugiere pre-breakout volátil-contracting, pero la lógica no detecta nada de eso.

Viola Principio 9 (institutional sponsorship), Principio 1 (transitions > snapshots — la dirección no se considera) y Principio 7 (interpretabilidad — el nombre miente sobre lo que detecta).

## What Changes

**CONTINUATION_HOLDING — nueva semántica:**
- Agregar `_is_quality_leader()` como prerequisito (8 gates, incluye sma150 > sma200*1.05)
- Agregar `distance_to_ema9_atr >= 0` (no rompió EMA9)
- Agregar `ema21_distance_change >= 0` (subiendo o lateral, no cayendo a EMA21)
- Mantener rango `0 ≤ distance_to_ema21_atr ≤ 1.5`

**STABILIZING — nueva semántica (pre-breakout en uptrend):**
- Agregar `_is_quality_leader()` como prerequisito
- Cambiar zona: `0 ≤ distance_to_ema21_atr ≤ 2.0`
- Reemplazar criterio actual (rs/vol planos) por `weekly_tightness >= 0.3` + `volume_change_pct < 0`
- Complementa COMPRESSING (que opera debajo de EMA21)

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities

- `transition-engine`: dos Requirements modificados — uno por cada transition type. Endurecen los criterios para que solo líderes institucionales con estructura confirmada aparezcan como "continuación" o "estabilización".

## Non-goals

- No tocar `ENTERING_PULLBACK` (recién auditado).
- No tocar `RECLAIMING`, `COMPRESSING`, `VOLUME_DRY_UP`, `SUPPORT_HOLDING`, `FLUSH_AND_RECOVER` ni los bearish — son ejes separados de la auditoría.
- No cambiar la posición de prioridad en la cadena de detección.
- No agregar nuevos transition types.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/services/transition_engine.py` | Reescribir blocks #10 (CONTINUATION_HOLDING) y #11 (STABILIZING) en `_determine_operational_transition()` |
| Spec previo `redefine-entering-pullback/specs/transition-engine/spec.md` | Sin cambios — este change toca otros transitions |
| Frontend `LiveTransitionFeed.tsx` | Sin cambios — solo cambia el filtrado backend, el render queda igual |

Sin migración, sin recálculo, sin schema. Los feeds futuros tendrán menos `continuation_holding` (filtra ~80% de los actuales por falta de quality gates).
