## 1. Backend — helper _dist_to_setup_pct() [transition-engine]

- [ ] 1.1 En `backend/app/api/v1/endpoints/transitions.py`, agregar función helper:
  ```python
  def _dist_to_setup_pct(metrics: StockMetrics, transition: str) -> float | None:
      price = metrics.current_price
      atr = metrics.atr
      if not price or not atr:
          return None
      d9 = metrics.distance_to_ema9_atr
      d21 = metrics.distance_to_ema21_atr
      if transition == 'entering_pullback' and d9 is not None and abs(d9) <= 0.5:
          ema_price = price - (d9 * atr)
      elif d21 is not None:
          ema_price = price - (d21 * atr)
      else:
          return None
      return round((ema_price - price) / price * 100, 1)
  ```

## 2. Backend — agregar campos al response de /live [transition-engine]

- [ ] 2.1 En el bloque `transitions.append({...})` del endpoint `/live`, agregar:
  ```python
  "current_price":     round(current.current_price, 2) if current.current_price else None,
  "change_pct":        round(current.perf_1w / 5, 1) if current.perf_1w else None,
  "dist_to_setup_pct": _dist_to_setup_pct(current, op_transition.transition.value),
  "dist_ema_label":    "EMA9" if (
      op_transition.transition.value == 'entering_pullback' and
      current.distance_to_ema9_atr is not None and
      abs(current.distance_to_ema9_atr) <= 0.5
  ) else "EMA21",
  ```

## 3. Backend — agregar campos al response de /actionable [transition-engine]

- [ ] 3.1 En el bloque `actionable.append({...})` del endpoint `/actionable`, agregar los mismos 4 campos usando la variable `setup` (que es el StockMetrics actual):
  ```python
  "current_price":     round(setup.current_price, 2) if setup.current_price else None,
  "change_pct":        round(setup.perf_1w / 5, 1) if setup.perf_1w else None,
  "dist_to_setup_pct": _dist_to_setup_pct(setup, _classify_setup_type(setup)),
  "dist_ema_label":    "EMA9" if _classify_setup_type(setup) == "ema9_pullback" else "EMA21",
  ```

## 4. Frontend — LiveTransitionFeed.tsx [transition-engine]

- [ ] 4.1 Agregar campos al type `TransitionEvent`:
  ```ts
  current_price?: number
  change_pct?: number
  dist_to_setup_pct?: number
  dist_ema_label?: string
  ```
- [ ] 4.2 En el row 1 (línea del símbolo), agregar inline después del badge de transition:
  ```tsx
  {event.current_price && (
    <span className="text-xs font-mono text-foreground ml-auto">
      ${event.current_price.toFixed(2)}
    </span>
  )}
  {event.change_pct != null && (
    <span className={`text-xs font-mono ${event.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
      {event.change_pct >= 0 ? '+' : ''}{event.change_pct.toFixed(1)}%
    </span>
  )}
  {event.dist_to_setup_pct != null && (
    <span className="text-xs text-muted-foreground">
      {event.dist_to_setup_pct > 0 ? '+' : ''}{event.dist_to_setup_pct.toFixed(1)}% {event.dist_ema_label}
    </span>
  )}
  ```

## 5. Frontend — TopActionableSetups.tsx [transition-engine]

- [ ] 5.1 Idem LiveTransitionFeed — agregar los mismos 4 campos al type del setup y renderizar inline con el mismo formato.

## 6. Validación [transition-engine]

- [ ] 6.1 Abrir el dashboard y verificar que cada fila del Live Feed muestra `$precio +/-X.X% Y.Y% EMAN`
- [ ] 6.2 Verificar que un setup `entering_pullback` con d9 <= 0.5 muestra "EMA9", el resto muestra "EMA21"
- [ ] 6.3 Verificar que stocks sin precio no rompen el componente (null silencioso)
- [ ] 6.4 Verificar que el cambio en % tiene color correcto (verde/rojo)
