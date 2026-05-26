## 1. Reescribir block CONTINUATION_HOLDING en transition_engine.py [transition-engine]

- [ ] 1.1 Reemplazar el block actual `if 0 <= ema21 <= 1.5: return CONTINUATION_HOLDING` con la nueva lógica:
  ```python
  # 10. Continuation holding — quality leader holding above EMA21,
  # still above EMA9 (no broke close support), stable or rising distance.
  if (self._is_quality_leader(current_metrics) and
      ema9 >= 0 and
      0 <= ema21 <= 1.5 and
      ema21_distance_change >= 0):
      return OperationalTransition.CONTINUATION_HOLDING
  ```
- [ ] 1.2 Actualizar el comentario inline del block para reflejar los nuevos gates

## 2. Reescribir block STABILIZING en transition_engine.py [transition-engine]

- [ ] 2.1 Mover el block STABILIZING para que sea evaluado ANTES de CONTINUATION_HOLDING (passa de #11 a #10, CONTINUATION_HOLDING queda como #11)
- [ ] 2.2 Reemplazar la lógica actual (`|rs_change|<1 and |vol_change|<15`) con:
  ```python
  # 10. Stabilizing — quality leader with structure tightening and volume
  # contracting above EMA21. Pre-breakout uptrend complement of COMPRESSING.
  tightness = current_metrics.weekly_tightness or 0
  if (self._is_quality_leader(current_metrics) and
      0 <= ema21 <= 2.0 and
      tightness >= 0.3 and
      volume_change_pct < 0):
      return OperationalTransition.STABILIZING
  ```

## 3. Validación post-cambio [transition-engine]

- [ ] 3.1 Ejecutar `curl http://localhost:8000/api/v1/transitions/live?limit=20`
- [ ] 3.2 Confirmar que NVDA, AMN, MEI, NN, AAON NO aparecen como continuation_holding (fallan quality gates por sma_sep < 5%)
- [ ] 3.3 Confirmar que AXTI, AAOI (con sma_sep > 5%) siguen apareciendo si su d9 >= 0
- [ ] 3.4 Confirmar que aparece al menos un stabilizing si hay líderes con weekly_tightness alto

## 4. Edge cases [transition-engine]

- [ ] 4.1 Buscar un stock con `weekly_tightness IS NULL` y confirmar que el `or 0` previene crash
- [ ] 4.2 Verificar que un líder con ema21=0 (exactamente en EMA21) y ema21_distance_change=0 cae como continuation_holding (boundary case)
- [ ] 4.3 Verificar que un líder con ema21=1.6 (apenas fuera del rango 1.5) cae al fallback, no a continuation_holding
