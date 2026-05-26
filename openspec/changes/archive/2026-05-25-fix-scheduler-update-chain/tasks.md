## 1. Agregar `_slow_running` flag y helper `_get_slow_symbols_and_date()` [universe-management]

- [ ] 1.1 En `__init__`, agregar `self._slow_running = False`
- [ ] 1.2 Agregar helper:
  ```python
  async def _get_slow_symbols_and_date(self, db) -> tuple:
      from sqlalchemy import select, func
      from app.models.stock import StockPrice
      today = (await db.execute(select(func.max(StockPrice.date)))).scalar()
      if not today:
          return [], None
      result = await db.execute(
          select(StockPrice.symbol).where(StockPrice.date == today).distinct()
      )
      symbols = [r[0] for r in result.fetchall()]
      logger.info(f"SLOW cycle: {len(symbols)} symbols with price for {today}")
      return symbols, str(today)
  ```

## 2. Reescribir `trigger_metrics_update` con backward compat y write-protection [universe-management]

- [ ] 2.1 Cambiar firma a `async def trigger_metrics_update(self, limit=None, symbols=None)`
- [ ] 2.2 Implementar lógica:
  ```python
  async def trigger_metrics_update(self, limit=None, symbols=None):
      from sqlalchemy import select
      from app.models.stock import StockMetrics
      if self._slow_running:
          logger.info("SLOW cycle still running — skipping")
          return 0
      self._slow_running = True
      try:
          async with self._get_db() as db:
              snapshot_date = None
              if symbols is None:
                  symbols, snapshot_date = await self._get_slow_symbols_and_date(db)
              if not symbols:
                  return 0
              if limit:
                  symbols = symbols[:limit]
              calculator = MetricsCalculator(db)
              count = 0
              for sym in symbols:
                  if snapshot_date:
                      existing = await db.execute(
                          select(StockMetrics.date)
                          .where(StockMetrics.symbol == sym, StockMetrics.date >= snapshot_date)
                          .limit(1)
                      )
                      if existing.scalar():
                          continue
                  try:
                      await calculator.calculate_metrics_for_symbol(sym)
                      count += 1
                  except Exception:
                      continue
              logger.info(f"SLOW metrics calculated for {count} symbols")
              await db.commit()
          asyncio.create_task(self._broadcast_metrics_updated(count, tier='all'))
          return count
      finally:
          self._slow_running = False
  ```

## 3. Modificar `_scheduler_loop`: price await + FAST chain [universe-management]

- [ ] 3.1 Reemplazar el bloque de price update:
  ```python
  if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
      logger.info("Triggering price update")
      try:
          await self._update_prices()
      except Exception as e:
          logger.error(f"Price update failed (continuing): {e}")
      last_price_update = now
      # Forzar FAST metrics inmediatamente con precios frescos
      await self.trigger_fast_metrics_update()
      last_fast_metrics_update = now
      await asyncio.sleep(30)
      continue
  ```
- [ ] 3.2 Eliminar el `last_metrics_update` hardcoded `limit=3125` en el loop:
  ```python
  if last_metrics_update is None or (now - last_metrics_update).total_seconds() >= 1800:
      logger.info("Triggering SLOW metrics update")
      await self.trigger_metrics_update()  # sin limit, usa todos los símbolos con precio de hoy
      last_metrics_update = now
  ```

## 4. Modificar startup: price first, SLOW background [universe-management]

- [ ] 4.1 Reemplazar startup actual:
  ```python
  # ANTES:
  logger.info("Triggering initial metrics update")
  await self.trigger_metrics_update(limit=3125)
  last_metrics_update = datetime.now(et_tz)
  
  # DESPUÉS:
  logger.info("Startup: fetching fresh prices first")
  try:
      await self._update_prices()
  except Exception as e:
      logger.error(f"Startup price update failed: {e}")
  last_price_update = datetime.now(et_tz)  # FIX: evita doble download en primer tick
  
  logger.info("Startup: initial SLOW metrics calculation (background)")
  asyncio.create_task(self.trigger_metrics_update())
  last_metrics_update = datetime.now(et_tz)
  ```

## 5. Validación [universe-management]

- [ ] 5.1 Reiniciar scheduler. Verificar en log la secuencia:
  ```
  Startup: fetching fresh prices first
  Price update complete: XXXX symbols
  Startup: initial SLOW metrics calculation (background)
  SLOW cycle: XXXX symbols with price for YYYY-MM-DD
  Scheduler loop started
  ```
- [ ] 5.2 Esperar 5 min: verificar FAST cycle dispara sin esperar al SLOW
- [ ] 5.3 Esperar al primer ciclo de precio del loop (15 min): verificar secuencia:
  ```
  Triggering price update
  Price update complete: XXXX symbols
  FAST cycle: XXX TIER 1 + YYY institutional = ZZZ symbols
  FAST metrics updated for ZZZ symbols
  ```
- [ ] 5.4 Verificar que la brecha precio/métricas baja a ≈0 tras un SLOW completo:
  ```sql
  SELECT COUNT(*) FROM (
    SELECT sp.symbol FROM (SELECT symbol, MAX(date) date FROM stock_prices GROUP BY symbol) sp
    JOIN (SELECT symbol, MAX(date) date FROM stock_metrics GROUP BY symbol) sm USING (symbol)
    WHERE sp.date > sm.date
  ) t;
  ```
- [ ] 5.5 Verificar que si el SLOW está corriendo y dispara el timer, aparece `"SLOW cycle still running — skipping"` en el log
- [ ] 5.6 Verificar que el endpoint manual `/api/v1/metrics/update?limit=100` sigue funcionando (backward compat)
