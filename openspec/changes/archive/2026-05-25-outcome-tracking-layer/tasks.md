## 1. Migración Alembic + Modelo [outcome-tracking]

- [ ] 1.1 Generar migración: `alembic revision -m "create_transition_observations"`
- [ ] 1.2 Editar migración con:
  ```python
  def upgrade():
      op.create_table(
          'transition_observations',
          sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
          sa.Column('symbol', sa.String(10), nullable=False),
          sa.Column('transition_type', sa.String(40), nullable=False),
          sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
          sa.Column('date_detected', sa.Date(), nullable=False),
          # context snapshot
          sa.Column('regime_at_detection', sa.String(20), nullable=True),
          sa.Column('price_at_detection', sa.Float(), nullable=True),
          sa.Column('ema9_at_detection', sa.Float(), nullable=True),
          sa.Column('ema21_at_detection', sa.Float(), nullable=True),
          sa.Column('ema50_at_detection', sa.Float(), nullable=True),
          sa.Column('atr_at_detection', sa.Float(), nullable=True),
          sa.Column('rs_spy_at_detection', sa.Float(), nullable=True),
          sa.Column('adr_percent_at_detection', sa.Float(), nullable=True),
          sa.Column('vcp_score_at_detection', sa.Float(), nullable=True),
          sa.Column('relative_volume_at_detection', sa.Float(), nullable=True),
          sa.Column('weekly_tightness_at_detection', sa.Float(), nullable=True),
          # outcome fields
          sa.Column('price_1d', sa.Float(), nullable=True),
          sa.Column('price_5d', sa.Float(), nullable=True),
          sa.Column('price_20d', sa.Float(), nullable=True),
          sa.Column('pct_1d', sa.Float(), nullable=True),
          sa.Column('pct_5d', sa.Float(), nullable=True),
          sa.Column('pct_20d', sa.Float(), nullable=True),
          sa.Column('max_gain_within_10d', sa.Float(), nullable=True),
          sa.Column('max_drawdown_within_10d', sa.Float(), nullable=True),
          sa.Column('max_gain_atr_within_10d', sa.Float(), nullable=True),
          sa.Column('max_drawdown_atr_within_10d', sa.Float(), nullable=True),
          sa.Column('reached_ema21_within_10d', sa.Boolean(), nullable=True),
          sa.Column('broke_ema50_within_10d', sa.Boolean(), nullable=True),
          sa.Column('outcome_status', sa.String(20), nullable=False, server_default='PENDING'),
          sa.Column('outcome_evaluated_at', sa.DateTime(timezone=True), nullable=True),
      )
      op.create_index('ix_obs_symbol_type_date', 'transition_observations', 
                      ['symbol', 'transition_type', 'date_detected'], unique=True)
      op.create_index('ix_obs_pending', 'transition_observations', 
                      ['outcome_status', 'date_detected'],
                      postgresql_where=sa.text("outcome_status = 'PENDING'"))
      op.create_index('ix_obs_aggregation', 'transition_observations',
                      ['transition_type', 'regime_at_detection', 'outcome_status'])
  
  def downgrade():
      op.drop_index('ix_obs_aggregation', 'transition_observations')
      op.drop_index('ix_obs_pending', 'transition_observations')
      op.drop_index('ix_obs_symbol_type_date', 'transition_observations')
      op.drop_table('transition_observations')
  ```
- [ ] 1.3 Agregar modelo `TransitionObservation` en `app/models/stock.py` con los mismos campos
- [ ] 1.4 Ejecutar `alembic upgrade head`

## 2. OutcomeTracker service [outcome-tracking]

- [ ] 2.1 Crear `backend/app/services/outcome_tracker.py`:
  ```python
  from datetime import date, datetime, timedelta
  from typing import Optional, Iterable
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import select, and_
  from sqlalchemy.dialects.postgresql import insert
  from app.models.stock import TransitionObservation, StockPrice, StockMetrics
  
  PRE_RECLAIM = {'entering_pullback', 'volume_dry_up', 'compressing', 
                 'flush_and_recover', 'support_holding'}
  RECLAIM_CONT = {'reclaiming', 'continuation_holding', 'stabilizing'}
  DETERIORATION = {'weakening', 'distribution', 'failing'}
  
  class OutcomeTracker:
      def __init__(self, db: AsyncSession):
          self.db = db
      
      async def record_observation(self, symbol, transition_value, current_metrics, regime, date_detected):
          """Idempotent insert via ON CONFLICT DO NOTHING."""
          if transition_value == 'stable':
              return
          stmt = insert(TransitionObservation).values(
              symbol=symbol.upper(),
              transition_type=transition_value,
              date_detected=date_detected,
              regime_at_detection=regime,
              price_at_detection=current_metrics.current_price,
              ema9_at_detection=current_metrics.ema9,
              ema21_at_detection=current_metrics.ema21,
              ema50_at_detection=current_metrics.ema50,
              atr_at_detection=current_metrics.atr,
              rs_spy_at_detection=current_metrics.relative_strength_spy,
              adr_percent_at_detection=current_metrics.adr_percent,
              vcp_score_at_detection=current_metrics.vcp_score,
              relative_volume_at_detection=current_metrics.relative_volume,
              weekly_tightness_at_detection=current_metrics.weekly_tightness,
          ).on_conflict_do_nothing(index_elements=['symbol', 'transition_type', 'date_detected'])
          await self.db.execute(stmt)
          # commit handled by caller's session
      
      async def evaluate_pending_outcomes(self, as_of_date: date):
          """Fill outcome fields for observations with enough elapsed time."""
          # Fetch PENDING observations with date_detected at least 1 day old
          cutoff_1d = as_of_date - timedelta(days=1)
          q = select(TransitionObservation).where(and_(
              TransitionObservation.outcome_status == 'PENDING',
              TransitionObservation.date_detected <= cutoff_1d
          ))
          observations = (await self.db.execute(q)).scalars().all()
          for obs in observations:
              await self._evaluate_one(obs, as_of_date)
          await self.db.commit()
      
      async def _evaluate_one(self, obs, as_of_date):
          # Fetch stock_prices from obs.date_detected to obs.date_detected + 21d
          end_date = obs.date_detected + timedelta(days=30)  # buffer for weekends
          q = select(StockPrice).where(and_(
              StockPrice.symbol == obs.symbol,
              StockPrice.date > obs.date_detected.isoformat(),
              StockPrice.date <= end_date.isoformat()
          )).order_by(StockPrice.date)
          prices = (await self.db.execute(q)).scalars().all()
          if not prices:
              if (as_of_date - obs.date_detected).days >= 15:
                  obs.outcome_status = 'INSUFFICIENT_DATA'
                  obs.outcome_evaluated_at = datetime.utcnow()
              return
          
          # Build trading-day indexed list
          # prices[0] = T+1, prices[1] = T+2, ... (only trading days)
          base = obs.price_at_detection
          atr = obs.atr_at_detection or 0
          
          if len(prices) >= 1 and obs.price_1d is None:
              obs.price_1d = prices[0].close
              obs.pct_1d = (prices[0].close - base) / base * 100 if base else None
          if len(prices) >= 5 and obs.price_5d is None:
              obs.price_5d = prices[4].close
              obs.pct_5d = (prices[4].close - base) / base * 100 if base else None
          if len(prices) >= 20 and obs.price_20d is None:
              obs.price_20d = prices[19].close
              obs.pct_20d = (prices[19].close - base) / base * 100 if base else None
          
          # 10d window classification (needs at least 10 trading days)
          if len(prices) >= 10 and obs.outcome_status == 'PENDING':
              window = prices[:10]
              highs = [p.high for p in window]
              lows = [p.low for p in window]
              closes = [p.close for p in window]
              obs.max_gain_within_10d = (max(highs) - base) / base * 100 if base else None
              obs.max_drawdown_within_10d = (min(lows) - base) / base * 100 if base else None
              if atr > 0:
                  obs.max_gain_atr_within_10d = (max(highs) - base) / atr
                  obs.max_drawdown_atr_within_10d = (min(lows) - base) / atr
              # reached EMA21 / broke EMA50 — use snapshot EMAs as approximation
              ema21 = obs.ema21_at_detection
              ema50 = obs.ema50_at_detection
              obs.reached_ema21_within_10d = bool(ema21 and max(closes) >= ema21)
              obs.broke_ema50_within_10d = bool(ema50 and min(closes) < ema50)
              obs.outcome_status = self._classify_outcome(obs)
              obs.outcome_evaluated_at = datetime.utcnow()
      
      def _classify_outcome(self, obs) -> str:
          t = obs.transition_type
          dd_atr = obs.max_drawdown_atr_within_10d
          gain_atr = obs.max_gain_atr_within_10d
          pct_5d = obs.pct_5d
          pct_10d = (obs.pct_5d * 2) if pct_5d is not None and obs.pct_20d is None else None
          # Note: we approximate pct_10d via pct_5d when 20d not available; if 20d present compute from prices is better
          
          if t in PRE_RECLAIM:
              if obs.broke_ema50_within_10d or (dd_atr is not None and dd_atr < -3.0):
                  return 'FAILURE'
              if obs.reached_ema21_within_10d and (dd_atr or 0) > -2.5:
                  return 'SUCCESS'
              return 'NEUTRAL'
          if t in RECLAIM_CONT:
              if pct_5d is not None and pct_5d < -3.0:
                  return 'FAILURE'
              if gain_atr is not None and gain_atr > 1.0 and (dd_atr or 0) > -1.5:
                  return 'SUCCESS'
              return 'NEUTRAL'
          if t in DETERIORATION:
              if pct_5d is not None and pct_5d > 3.0:
                  return 'FAILURE'
              # use close-of-day-10 (last close in window) for direction
              if obs.max_drawdown_within_10d is not None and obs.max_gain_within_10d is not None:
                  if obs.max_drawdown_within_10d < obs.max_gain_within_10d * -1:
                      return 'SUCCESS'
              return 'NEUTRAL'
          return 'NEUTRAL'
  ```

## 3. Regime snapshot cache [outcome-tracking]

- [ ] 3.1 Crear helper en `outcome_tracker.py` que cachee regime del día actual:
  ```python
  _regime_cache = {}  # {date_iso: regime_str}
  
  async def get_current_regime(db, today: date) -> str:
      key = today.isoformat()
      if key not in _regime_cache:
          # call MarketRegimeEngine.get_current_regime() (existing service)
          from app.services.market_regime_engine import MarketRegimeEngine
          engine = MarketRegimeEngine(db)
          regime = await engine.get_current_regime()
          _regime_cache.clear()  # invalidate previous days
          _regime_cache[key] = regime.value if hasattr(regime, 'value') else str(regime)
      return _regime_cache[key]
  ```

## 4. Wire en transition_engine.py [outcome-tracking]

- [ ] 4.1 En `TransitionEngine.calculate_operational_transition`, después de calcular `transition`, antes del return:
  ```python
  # Record observation (idempotent)
  if transition != OperationalTransition.STABLE:
      from app.services.outcome_tracker import OutcomeTracker, get_current_regime
      from datetime import date as date_cls
      try:
          today = date_cls.today()
          regime = await get_current_regime(self.db, today)
          tracker = OutcomeTracker(self.db)
          await tracker.record_observation(
              symbol=symbol,
              transition_value=transition.value,
              current_metrics=current_metrics,
              regime=regime,
              date_detected=today,
          )
      except Exception as e:
          logger.warning(f"Failed to record observation for {symbol}: {e}")
  ```

## 5. Wire en scheduler.py [outcome-tracking]

- [ ] 5.1 En `DataScheduler._scheduler_loop`, después del SLOW cycle exitoso, agregar:
  ```python
  # After SLOW cycle: evaluate pending outcomes
  try:
      from app.services.outcome_tracker import OutcomeTracker
      from datetime import date
      async with AsyncSessionLocal() as session:
          tracker = OutcomeTracker(session)
          await tracker.evaluate_pending_outcomes(date.today())
      logger.info("Evaluated pending outcomes")
  except Exception as e:
      logger.error(f"Outcome evaluation failed: {e}")
  ```

## 6. Endpoints API [outcome-tracking]

- [ ] 6.1 En `backend/app/api/v1/endpoints/transitions.py` agregar:
  ```python
  from statistics import mean, median
  from app.models.stock import TransitionObservation
  
  @router.get("/track-record")
  async def track_record(
      transition_type: str = Query(...),
      regime: Optional[str] = Query(None),
      days: int = Query(90, ge=1, le=365),
      db: AsyncSession = Depends(get_db),
  ):
      since = date.today() - timedelta(days=days)
      filters = [
          TransitionObservation.transition_type == transition_type.lower(),
          TransitionObservation.date_detected >= since,
          TransitionObservation.outcome_status != 'PENDING',
      ]
      if regime:
          filters.append(TransitionObservation.regime_at_detection == regime.lower())
      q = select(TransitionObservation).where(and_(*filters))
      rows = (await db.execute(q)).scalars().all()
      
      n = len(rows)
      if n == 0:
          return {"transition_type": transition_type, "regime": regime, "window_days": days,
                  "sample_size": 0, "success_rate": None, "failure_rate": None, "neutral_rate": None,
                  "avg_pct_5d": None, "avg_max_gain_atr_10d": None, "avg_max_drawdown_atr_10d": None,
                  "median_pct_5d": None, "minimum_sample_warning": "No data"}
      
      succ = sum(1 for r in rows if r.outcome_status == 'SUCCESS')
      fail = sum(1 for r in rows if r.outcome_status == 'FAILURE')
      neut = sum(1 for r in rows if r.outcome_status == 'NEUTRAL')
      pct5 = [r.pct_5d for r in rows if r.pct_5d is not None]
      gain_atr = [r.max_gain_atr_within_10d for r in rows if r.max_gain_atr_within_10d is not None]
      dd_atr = [r.max_drawdown_atr_within_10d for r in rows if r.max_drawdown_atr_within_10d is not None]
      
      warning = "Sample size below 30 — stats unreliable" if n < 30 else None
      
      return {
          "transition_type": transition_type, "regime": regime, "window_days": days,
          "sample_size": n,
          "success_rate": round(succ / n, 3),
          "failure_rate": round(fail / n, 3),
          "neutral_rate": round(neut / n, 3),
          "avg_pct_5d": round(mean(pct5), 2) if pct5 else None,
          "avg_max_gain_atr_10d": round(mean(gain_atr), 2) if gain_atr else None,
          "avg_max_drawdown_atr_10d": round(mean(dd_atr), 2) if dd_atr else None,
          "median_pct_5d": round(median(pct5), 2) if pct5 else None,
          "minimum_sample_warning": warning,
      }
  
  @router.get("/observations/{symbol}")
  async def observations_for_symbol(
      symbol: str,
      db: AsyncSession = Depends(get_db),
  ):
      q = (select(TransitionObservation)
           .where(TransitionObservation.symbol == symbol.upper())
           .order_by(TransitionObservation.detected_at.desc())
           .limit(50))
      rows = (await db.execute(q)).scalars().all()
      return [
          {
              "id": r.id, "transition_type": r.transition_type,
              "date_detected": r.date_detected.isoformat() if r.date_detected else None,
              "detected_at": r.detected_at.isoformat() if r.detected_at else None,
              "regime_at_detection": r.regime_at_detection,
              "price_at_detection": r.price_at_detection,
              "atr_at_detection": r.atr_at_detection,
              "outcome_status": r.outcome_status,
              "pct_1d": r.pct_1d, "pct_5d": r.pct_5d, "pct_20d": r.pct_20d,
              "max_gain_atr_10d": r.max_gain_atr_within_10d,
              "max_drawdown_atr_10d": r.max_drawdown_atr_within_10d,
              "reached_ema21_within_10d": r.reached_ema21_within_10d,
              "broke_ema50_within_10d": r.broke_ema50_within_10d,
          }
          for r in rows
      ]
  ```

## 7. Validación end-to-end [outcome-tracking]

- [ ] 7.1 Ejecutar migración. Verificar que tabla y 3 índices existen: `\d transition_observations` en psql.
- [ ] 7.2 Forzar un SLOW cycle o esperar al siguiente. Verificar que `SELECT COUNT(*) FROM transition_observations` > 0 dentro de 5 min.
- [ ] 7.3 Verificar dedup: ejecutar SLOW cycle dos veces seguidas, contar rows — debe ser igual antes y después.
- [ ] 7.4 Esperar ≥10 días o crear observation sintética con `date_detected = today - 12 days` y precios mock. Ejecutar `evaluate_pending_outcomes(today)`. Verificar que `outcome_status` queda SUCCESS/FAILURE/NEUTRAL.
- [ ] 7.5 Hit `GET /api/v1/transitions/observations/NVDA` — verificar response shape correcto.
- [ ] 7.6 Hit `GET /api/v1/transitions/track-record?transition_type=entering_pullback&days=90` — verificar response shape correcto (probablemente `sample_size = 0` los primeros días, lo cual es OK).

## 8. Documentación / memory [outcome-tracking]

- [ ] 8.1 Agregar memory entry `outcome_tracking_started.md` con: fecha de start, schema, definiciones de success, intervalo para re-calibración (90d).
- [ ] 8.2 Actualizar PRODUCT_BRAIN/NON_NEGOTIABLE_PRINCIPLES.md (o crear `EVOLUTION_LAYER.md`) explicando que el sistema ahora mide outcomes y que la calibración de thresholds en transition_engine debe revisarse contra track-record cada 90 días.
