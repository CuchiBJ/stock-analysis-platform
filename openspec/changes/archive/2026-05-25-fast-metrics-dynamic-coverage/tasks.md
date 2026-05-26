## 1. Extraer helper _get_fast_symbols() [universe-management]

- [ ] 1.1 En `backend/app/data/scheduler.py`, agregar el método `_get_fast_symbols()` a la clase `DataScheduler`:
  ```python
  async def _get_fast_symbols(self, db: AsyncSession) -> list[str]:
      """TIER 1 base + institutional quality stocks (live transitions candidates)."""
      from sqlalchemy import select, and_, func
      from app.models.stock import StockMetrics
      from app.models.universe import UniverseTier as UniverseTierModel

      latest_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
      if not latest_date:
          return []

      # TIER 1 symbols via stock_metrics (avoids instrument_id resolution complexity)
      tier1_result = await db.execute(
          select(StockMetrics.symbol)
          .where(StockMetrics.date == latest_date)
          .join(UniverseTierModel, UniverseTierModel.instrument_id == StockMetrics.symbol, isouter=True)
          .where(UniverseTierModel.tier == "tier_1")
          .limit(200)
      )
      tier1_symbols = {r[0] for r in tier1_result.fetchall()}

      # Institutional quality stocks — slightly relaxed thresholds vs live feed
      # to capture stocks about to qualify
      inst_result = await db.execute(
          select(StockMetrics.symbol)
          .where(and_(
              StockMetrics.date == latest_date,
              StockMetrics.avg_volume_10d >= 800_000,
              StockMetrics.adr_percent >= 3.0,
              StockMetrics.current_price >= 5.0,
              StockMetrics.perf_1y > 25,
              StockMetrics.current_price > StockMetrics.ema50,
              StockMetrics.current_price > StockMetrics.sma150,
              StockMetrics.sma150 > StockMetrics.sma200,
          ))
          .limit(200)
      )
      inst_symbols = {r[0] for r in inst_result.fetchall()}

      combined = list(tier1_symbols | inst_symbols)
      logger.info(
          f"FAST cycle: {len(tier1_symbols)} TIER 1 + "
          f"{len(inst_symbols - tier1_symbols)} institutional = {len(combined)} unique symbols"
      )
      return combined
  ```

## 2. Reemplazar bloque tier_query en trigger_fast_metrics_update() [universe-management]

- [ ] 2.1 Reemplazar el bloque actual:
  ```python
  tier_query = select(UniverseTierModel).where(UniverseTierModel.tier == "tier_1")
  tier_result = await db.execute(tier_query)
  tier1_symbols = [r.instrument_id for r in tier_result.scalars().all()]
  logger.info(f"Updating FAST metrics for {len(tier1_symbols)} TIER 1 symbols")
  ```
  Por:
  ```python
  tier1_symbols = await self._get_fast_symbols(db)
  ```

- [ ] 2.2 Subir el límite de `tier1_symbols[:200]` a `tier1_symbols[:300]` en el loop de cálculo

## 3. Validación [universe-management]

- [ ] 3.1 Esperar el próximo ciclo FAST (máximo 5 min) y verificar en el log:
  ```
  INFO: FAST cycle: X TIER 1 + Y institutional = Z unique symbols
  INFO: FAST metrics updated for Z TIER 1 symbols
  ```
- [ ] 3.2 Confirmar que WULF, LITE, HUT, CIFR aparecen en el log del FAST cycle
- [ ] 3.3 Verificar que el ciclo FAST tarda menos de 3 minutos (si tarda más, reducir límite a 250)
- [ ] 3.4 Confirmar que el feed `GET /api/v1/transitions/live` muestra métricas con fecha de hoy actualizada para los stocks que aparecen

## 4. Fallback de seguridad [universe-management]

- [ ] 4.1 Si la query institutional devuelve 0 resultados (métricas del día aún no calculadas), `_get_fast_symbols()` debe devolver solo los TIER 1 sin fallar. Verificar que esto ocurre graciosamente al inicio del día antes del primer SLOW cycle.
