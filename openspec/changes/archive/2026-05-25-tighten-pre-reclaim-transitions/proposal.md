## Why

Los cuatro transitions pre-reclaim (`VOLUME_DRY_UP`, `COMPRESSING`, `SUPPORT_HOLDING`, `FLUSH_AND_RECOVER`) no aplican quality gates ni límites de profundidad. Cualquier stock técnicamente en esa zona dispara el signal, sin importar si era un líder institucional o un stock en caída libre.

Auditoría del feed actual (2026-05-21, 151 stocks institucionales):
- Solo 5 stocks disparan pre-reclaim (ALM, CLS, AMKR, ICHR, MTZ) — todos parecen legítimos
- Pero sin quality gates, el feed también puede incluir stocks que nunca cumplieron Stage 2 y están simplemente cayendo
- Sin límite inferior de profundidad: un stock a -5 ATR de EMA21 puede disparar VOLUME_DRY_UP aunque estructuralmente esté roto

Viola Principio 9 (señal institucional primaria — el pre-reclaim solo es accionable si el stock era un líder antes de corrección) y Principio 2 (scarcity is signal — sin filtro, el feed se llena de señales débiles).

## What Changes

**VOLUME_DRY_UP**: agregar `_is_quality_leader()` + límite `ema21 >= -2.0` ATR.

**COMPRESSING**: agregar `_is_quality_leader()` + límite `ema21 >= -2.0` ATR.

**SUPPORT_HOLDING**: agregar `_is_quality_leader()` + redefinir como stock que perdió EMA9/EMA21 pero está arriba de EMA50 y rebotando (`ema21 < 0`, `ema50 >= -0.5`).

**FLUSH_AND_RECOVER**: agregar `_is_quality_leader()`. El límite ya existe (`-2.5 <= ema21 <= -0.5`).

## Capabilities

### New Capabilities
*(ninguna)*

### Modified Capabilities
- `transition-engine`: cuatro Requirements modificados — uno por transition.

## Non-goals

- No cambiar los thresholds de volumen/RS dentro de cada criterio (eso requiere calibración con datos).
- No tocar los transitions bearish (FAILING, DISTRIBUTION, WEAKENING) — próximo eje de auditoría.
- No cambiar la posición en la cascada de prioridades.

## Impact

| Archivo | Cambio |
|---|---|
| `backend/app/services/transition_engine.py` | Blocks #4, #5, #6, #8 en `_determine_operational_transition()` |
