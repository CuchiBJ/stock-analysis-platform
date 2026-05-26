## 1. Agregar gate `sma150 > sma200` a `_is_quality_leader()` [transition-engine]

- [ ] 1.1 En `backend/app/services/transition_engine.py`, agregar `m.sma200 is not None` al check de null-guards de `_is_quality_leader()`
- [ ] 1.2 Agregar la condición `m.sma150 > m.sma200` al return statement, entre `m.sma50 > m.sma150` y `range_52w_pct >= 0.60`
- [ ] 1.3 Actualizar el docstring de la función para incluir el octavo gate

## 2. Validación post-cambio [transition-engine]

- [ ] 2.1 Ejecutar `curl http://localhost:8000/api/v1/transitions/live?limit=20` y comparar el listado vs el pre-cambio
- [ ] 2.2 Para cada stock que se haya caído del feed, verificar con query SQL que efectivamente cumple `sma150 <= sma200`:
  ```sql
  SELECT symbol, ROUND(sma150::numeric, 2), ROUND(sma200::numeric, 2),
         CASE WHEN sma150 > sma200 THEN 'pass' ELSE 'fail' END
  FROM stock_metrics
  WHERE symbol IN (<lista de stocks que se cayeron>)
    AND date = (SELECT MAX(date) FROM stock_metrics);
  ```
- [ ] 2.3 Confirmar que stocks como AMN, INTC, MEI siguen apareciendo (líderes Stage 2 confirmados)
- [ ] 2.4 Confirmar que el endpoint sigue respondiendo en < 500ms

## 3. Edge cases [transition-engine]

- [ ] 3.1 Buscar 1 stock con `sma200 IS NULL` (data insuficiente) en la DB y confirmar que el guard previene crash
- [ ] 3.2 Buscar 1 stock con `sma150 = sma200` exacto (improbable pero teórico) y confirmar que falla el gate (>, no >=)
