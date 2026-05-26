## 1. Obtener latest_date antes de la query principal [transition-engine]

- [ ] 1.1 Al inicio de `get_live_transitions()`, agregar una query para obtener el último día con datos:
  ```python
  latest_date_result = await db.execute(
      select(func.max(StockMetrics.date))
  )
  latest_date = latest_date_result.scalar()
  if not latest_date:
      return []
  ```
- [ ] 1.2 Calcular `prev_date` como 3 días calendario antes de `latest_date` (cubre fines de semana y feriados):
  ```python
  from datetime import date, timedelta
  latest_dt = date.fromisoformat(latest_date) if isinstance(latest_date, str) else latest_date
  prev_date = (latest_dt - timedelta(days=3)).isoformat()
  ```

## 2. Reemplazar la query de 7 días por ventana de 2 días [transition-engine]

- [ ] 2.1 Reemplazar la línea `cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")` por el uso de `prev_date` ya calculado
- [ ] 2.2 En la query principal, reemplazar `_ACTIONABLE_FILTER` (que incluye EMA trigger en SQL) por solo `_INSTITUTIONAL_SETUP` más el filtro de fechas:
  ```python
  result = await db.execute(
      select(StockMetrics)
      .where(and_(
          StockMetrics.date >= prev_date,
          StockMetrics.date <= latest_date,
          _INSTITUTIONAL_SETUP,
      ))
      .order_by(StockMetrics.date.desc())
      .limit(1000)
  )
  ```

## 3. Agregar helper _passes_ema_trigger() y filtrar en Python [transition-engine]

- [ ] 3.1 Agregar función helper local en el endpoint (fuera de la función async, junto a `_ACTIONABLE_FILTER`):
  ```python
  def _passes_ema_trigger(metrics: StockMetrics) -> bool:
      ema9 = metrics.distance_to_ema9_atr or 999.0
      ema21 = metrics.distance_to_ema21_atr or 999.0
      return (-1.0 <= ema9 <= 0.5) or (-1.0 <= ema21 <= 0.5)
  ```
- [ ] 3.2 En el loop `for symbol, metrics_list in symbol_metrics.items()`, agregar verificación de freshness y trigger ANTES de calcular la transición:
  ```python
  current = metrics_list[0]
  # Solo procesar si el "current" es del día más reciente
  if str(current.date) != str(latest_date):
      continue
  # Solo procesar si está en zona de trigger hoy
  if not _passes_ema_trigger(current):
      continue
  ```
- [ ] 3.3 Eliminar el bloque `recently_above` (líneas 129–136) — ya no es necesario porque la ventana de 2 días garantiza que solo tenemos current y previous, no 3 períodos de lookback

## 4. Verificación [transition-engine]

- [ ] 4.1 Reiniciar el backend y ejecutar `curl http://localhost:8000/api/v1/transitions/live?limit=20` — confirmar que NBIS ya NO aparece (sus datos de hoy 21/5 están fuera de la zona de trigger)
- [ ] 4.2 Confirmar que los stocks que SÍ aparecen tienen `date == latest_date` inspeccionando la respuesta
- [ ] 4.3 Confirmar que la dirección (approaching) sigue siendo correcta para los setups que aparecen — verificar que la narrativa dice "EMA9" o "EMA21" y no es el fallback genérico
- [ ] 4.4 Simular el caso de fin de semana: verificar con un stock que tiene datos del viernes que el "previous" toma el jueves correctamente
