## 1. Agregar cálculo de ema9_distance_change [transition-engine]

- [ ] 1.1 En `backend/app/services/transition_engine.py`, método `calculate_operational_transition()` (cerca de línea 187), agregar el cálculo de `ema9_distance_change` junto al de `ema21_distance_change`:
  ```python
  ema9_distance_change = 0.0
  if (current_metrics.distance_to_ema9_atr is not None and
      previous_metrics.distance_to_ema9_atr is not None):
      ema9_distance_change = current_metrics.distance_to_ema9_atr - previous_metrics.distance_to_ema9_atr
  ```
- [ ] 1.2 Pasar `ema9_distance_change` como argumento adicional a `_determine_operational_transition()`
- [ ] 1.3 Agregar `ema9_distance_change: float = 0.0` como parámetro en la firma de `_determine_operational_transition()`

## 2. Agregar helper _is_quality_leader() [transition-engine]

- [ ] 2.1 En `transition_engine.py`, agregar el método privado `_is_quality_leader(self, m: StockMetrics) -> bool` con los 7 quality gates Minervini:
  - `perf_1y > 30.0`
  - `current_price > ema200`
  - `distance_to_ema50_atr > 0`
  - `sma50 > sma150`
  - `(high_52w - low_52w) / low_52w >= 0.60`
  - `(current_price - low_52w) / low_52w >= 0.70`
  - `adr_percent >= 3.0`
- [ ] 2.2 El método retorna `False` si cualquier campo requerido es `None`

## 3. Reemplazar condición ENTERING_PULLBACK [transition-engine]

- [ ] 3.1 En `_determine_operational_transition()` (línea ~663), reemplazar la condición actual:
  ```python
  # ANTES
  if (prev_ema21_atr is not None and prev_ema21_atr > 0 and
          ema21 < 0 and ema50 > -0.5):
      return OperationalTransition.ENTERING_PULLBACK
  ```
  por la nueva lógica:
  ```python
  # DESPUÉS
  if self._is_quality_leader(current_metrics):
      approaching_ema9 = (
          0 < (current_metrics.distance_to_ema9_atr or -1) <= 0.5 and
          ema9_distance_change < 0
      )
      approaching_ema21 = (
          0 < ema21 <= 1.0 and
          ema21_distance_change < 0
      )
      if approaching_ema9 or approaching_ema21:
          return OperationalTransition.ENTERING_PULLBACK
  ```

## 4. Actualizar narrativa [transition-engine]

- [ ] 4.1 En `_generate_operational_narrative()`, localizar la entrada de `ENTERING_PULLBACK` en el dict de narrativas y reemplazarla por lógica que distinga EMA9 vs EMA21:
  - Si `distance_to_ema9_atr` disponible y ≤ 0.5: usar `"Approaching EMA9 — leader pulling back to fast EMA. Watch for support."`
  - Si `distance_to_ema21_atr` disponible y ≤ 1.0: usar `"Approaching EMA21 — leader testing key swing support. Controlled pullback."`
  - Fallback: `"Leader approaching key EMA. Quality setup forming."`

## 5. Verificación [transition-engine]

- [ ] 5.1 Reiniciar el backend (`uvicorn app.main:app --reload`) y ejecutar `curl http://localhost:8000/api/v1/transitions/live?limit=20` — confirmar que ENTERING_PULLBACK solo aparece para stocks con perf_1y > 30% y distancia decreciente a EMA
- [ ] 5.2 Verificar con LUNR: debe aparecer como ENTERING_PULLBACK si su distancia a EMA9 es ≤ 0.5 ATR y decreciente
- [ ] 5.3 Verificar que TER, FN, SGML, CLS no aparecen como ENTERING_PULLBACK
- [ ] 5.4 Verificar que la narrativa en el feed dice "EMA9" o "EMA21" según corresponda
- [ ] 5.5 Abrir el dashboard en `localhost:3000` y confirmar que el Live Transition Feed muestra los setups correctos
