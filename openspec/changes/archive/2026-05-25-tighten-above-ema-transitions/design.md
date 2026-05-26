## Context

El motor `_determine_operational_transition()` evalúa 12 transition types en cascada. Los blocks #10 y #11 (CONTINUATION_HOLDING y STABILIZING) operan sobre stocks arriba de EMA21 pero tienen criterios estructuralmente débiles:

```python
# 10. Continuation holding
if 0 <= ema21 <= 1.5:
    return OperationalTransition.CONTINUATION_HOLDING

# 11. Stabilizing
if abs(rs_change) < 1 and abs(volume_change_pct) < 15:
    return OperationalTransition.STABILIZING
```

CONTINUATION_HOLDING dispara para cualquier stock entre 0 y 1.5 ATR sobre EMA21 — sin perf_1y, sin SMA chain, sin dirección. STABILIZING es un fallback que solo verifica que las métricas no cambien mucho, sin contexto institucional.

Datos reales del feed (post-auditoría ENTERING_PULLBACK):
| Symbol | perf_1y | sma_sep% | d9 ATR | d21 ATR | Es líder real? |
|---|---|---|---|---|---|
| NVDA | 22% | 1.3% | -0.15 | 0.66 | NO (perf, sep) |
| AMN | 52% | 0.0% | -0.52 | 0.37 | NO (sep, rompió EMA9) |
| MEI | 73% | 0.4% | 0.21 | 0.87 | NO (sep) |
| AAON | 63% | 1.7% | 0.16 | 1.11 | NO (sep) |
| AXTI | 5729% | 29% | 0.48 | 1.08 | SÍ |
| AAOI | 661% | 19% | -0.05 | 0.25 | borderline (EMA9) |

## Goals / Non-Goals

**Goals:**
- CONTINUATION_HOLDING refleja "líder Stage 2 confirmado, sosteniéndose en zona operable" — no "cualquier stock arriba de EMA21".
- STABILIZING captura el patrón pre-breakout institucional: líder con volatilidad contrayéndose en uptrend.
- Coherencia entre transitions: si un stock falla quality gates para ENTERING_PULLBACK, tampoco debe pasar para CONTINUATION_HOLDING.
- AMN tipo de stock (rompió EMA9, sma_sep~0) NO debe aparecer en ninguna de las dos.

**Non-Goals:**
- No diseñar nuevos transition types.
- No alterar la cascada de prioridades (orden de evaluación).
- No tocar el resto de transitions en este change.

## Decisions

### Decisión 1: CONTINUATION_HOLDING usa los mismos 8 gates de ENTERING_PULLBACK

**Opción A (elegida): reutilizar `_is_quality_leader()` como prerequisito**

```python
if (self._is_quality_leader(current_metrics) and
    0 <= ema9 and  # no rompió EMA9
    0 <= ema21 <= 1.5 and
    ema21_distance_change >= 0):  # no cayendo a EMA21
    return OperationalTransition.CONTINUATION_HOLDING
```

- Pro: una sola definición de "líder institucional", evita drift entre transitions.
- Pro: si se afina `_is_quality_leader`, ambos transitions mejoran a la vez.

**Opción B descartada: gates separados más laxos**
- Justificación de descarte: el usuario eligió explícitamente "Quality leader completo (8 gates + sma_sep 5%)".

### Decisión 2: CONTINUATION_HOLDING exige `distance_to_ema9_atr >= 0`

El usuario eligió: stocks que rompieron EMA9 (d9 < 0) pero siguen arriba de EMA21 NO son continuation. Quedan en otro estado (cae al fallback de la cascada).

Esto distingue:
- **Continuation completa**: precio arriba de EMA9 y EMA21
- **Pullback en proceso**: rompió EMA9, testeando EMA21 → ENTERING_PULLBACK (ya cubierto si está cayendo) o sin transition específica.

### Decisión 3: CONTINUATION_HOLDING exige `ema21_distance_change >= 0`

Stock que se acerca a EMA21 desde arriba → ENTERING_PULLBACK (más informativo).
Stock que se sostiene o se aleja de EMA21 → CONTINUATION_HOLDING (lo que el nombre indica).

Sin este check, un stock cayendo a EMA21 dentro del rango [0, 1.5] entraba como continuation aunque debería ser pullback.

### Decisión 4: STABILIZING se redefine como pre-breakout en uptrend

Criterio actual (`|rs_change|<1 AND |vol_change|<15`) detecta "no pasa nada", que no es accionable. Lo redefinimos:

```python
if (self._is_quality_leader(current_metrics) and
    0 <= ema21 <= 2.0 and
    (current_metrics.weekly_tightness or 0) >= 0.3 and
    volume_change_pct < 0):
    return OperationalTransition.STABILIZING
```

- `weekly_tightness >= 0.3`: estructura semanal ajustada (rangos contrayéndose)
- `volume_change_pct < 0`: volumen también baja (clásico pre-breakout Minervini)
- Zone 0-2 ATR sobre EMA21: stock todavía en zona operable, no extendido

Es el complemento alcista de COMPRESSING (que opera abajo de EMA21). Misma semántica de volatility contraction, distinta posición.

### Decisión 5: STABILIZING va antes de CONTINUATION_HOLDING en la cascada

Si un stock cumple ambos, STABILIZING es más informativo (pre-breakout activo) que CONTINUATION_HOLDING (sosteniéndose). Por lo tanto, evaluar STABILIZING primero.

## Risks / Trade-offs

**[Riesgo 1: feed con muy pocos CONTINUATION_HOLDING después del cambio]**
→ Aceptado. Scarcity es señal (Principio 2). Si solo 1-2 líderes verdaderos están sosteniéndose, el feed lo refleja. Mejor que el ruido actual de 12 falsos positivos.

**[Riesgo 2: stocks que rompieron EMA9 quedan sin clasificar]**
→ Caen al fallback de la cascada (STABILIZING, STABLE, o RECLAIMING si está cerca de EMA21). Si ninguno coincide, terminan en STABLE — que ya filtramos del feed.

**[Riesgo 3: STABILIZING puede solapar con COMPRESSING en stocks borderline]**
→ No solapan: COMPRESSING exige `ema21 < -0.3` (debajo), STABILIZING `0 ≤ ema21 ≤ 2.0` (arriba). Mutuamente excluyentes por posición.

**[Riesgo 4: weekly_tightness >= 0.3 podría ser muy estricto/laxo]**
→ Monitorear post-deploy. Si nadie pasa STABILIZING en una semana, bajar a 0.2. Si demasiados, subir a 0.4.

## Migration Plan

1. Editar `_determine_operational_transition()` en `transition_engine.py`:
   - Reordenar: STABILIZING (#11) antes de CONTINUATION_HOLDING (#10).
   - Reescribir lógica de ambos según specs.
2. Verificar feed `GET /api/v1/transitions/live?limit=20`.
3. Confirmar que AMN, MEI, NVDA, NN, AAON ya no aparecen como continuation_holding.
4. Confirmar que AXTI, FLEX, RKLB (líderes con sma_sep alto) siguen apareciendo.

Rollback: revertir los dos blocks, sin migración.

## Open Questions

*(ninguna — todos los parámetros confirmados por el usuario en la sesión de auditoría)*
