## 1. Fix fórmula en metrics_calculator.py [universe-management]

- [ ] 1.1 En `backend/app/data/ingestors/metrics_calculator.py`, método `_calculate_weekly_tightness(df)`: calcular `daily_atr` como el promedio de los últimos 14 días del true range diario (`max(high-low, |high-prev_close|, |low-prev_close|)`)
- [ ] 1.2 En el mismo método: filtrar el DataFrame semanal `weekly` para retener solo semanas donde `volume > 0`. Si quedan menos de 3 semanas activas en `weekly.tail(4)`, retornar `0.0`
- [ ] 1.3 Reemplazar la línea `weekly['range_pct'] = (weekly['high'] - weekly['low']) / weekly['close'] * 100` por `weekly['range_atr'] = (weekly['high'] - weekly['low']) / daily_atr` (guardar el ATR en variable antes del resample)
- [ ] 1.4 Agregar guard: si `daily_atr == 0`, retornar `0.0` antes de cualquier cálculo
- [ ] 1.5 Actualizar la línea de retorno de `1.0 / (1.0 + recent_tightness)` para usar `recent_range_atr = weekly['range_atr'].tail(4).mean()` en vez de `recent_tightness`
- [ ] 1.6 Actualizar el docstring del método para describir que el resultado es ATR-normalizado y que semanas con volumen cero se excluyen

## 2. Restaurar threshold del scanner [universe-management]

- [ ] 2.1 En `backend/app/services/quality_swing_scanner_service.py`, cambiar `StockMetrics.weekly_tightness > 0.02` de vuelta a `StockMetrics.weekly_tightness > 0.3`
- [ ] 2.2 Actualizar el comentario en el docstring de `get_quality_swing_setups` de `weekly_tightness > 0.02` a `weekly_tightness > 0.3 (ATR-normalizado)`

## 3. Verificación de la fórmula antes de recalcular [universe-management]

- [ ] 3.1 Escribir un test rápido en Python (puede ser un script temporal) que ejercite `_calculate_weekly_tightness()` con datos sintéticos: (a) un stock con 4 semanas de volumen cero debe retornar 0.0, (b) un stock con rango semanal = 0.5x ATR debe retornar ≈ 0.67
- [ ] 3.2 Confirmar que el test pasa antes de continuar

## 4. Recalcular métricas [universe-management]

- [ ] 4.1 Correr `python scripts/recalculate_metrics_with_atr.py` desde el directorio `/stock-analysis-platform/backend/` para repoblar `stock_metrics` con los valores corregidos
- [ ] 4.2 Confirmar que el script termina sin errores

## 5. Verificación post-recalculación [universe-management]

- [ ] 5.1 Ejecutar esta query en la DB: `SELECT symbol, weekly_tightness FROM stock_metrics WHERE symbol IN ('LITE', 'NOK', 'HP') ORDER BY symbol, date DESC LIMIT 10` — confirmar que los valores están en el rango 0.3–0.8 (no 0.03–0.10 como antes)
- [ ] 5.2 Ejecutar `curl "http://localhost:8000/api/v1/quality-swing-scanner/?min_score=60"` y confirmar que devuelve stocks institucionales reales
- [ ] 5.3 Abrir el scanner en el browser (`localhost:3000/dashboard`) y confirmar que la tabla muestra resultados con los sliders en posición default
- [ ] 5.4 Verificar en DB que stocks con avg_volume_10d=0 tienen `weekly_tightness = 0.0` o NULL: `SELECT count(*) FROM stock_metrics WHERE avg_volume_10d = 0 AND weekly_tightness > 0.3`— debe retornar 0
