from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.models.stock import TransitionObservation, StockPrice
import logging

logger = logging.getLogger(__name__)

PRE_RECLAIM = {'entering_pullback', 'volume_dry_up', 'compressing', 'flush_and_recover', 'support_holding'}
BREAKOUT = {'breakout'}
RECLAIM_CONT = {'reclaiming', 'continuation_holding', 'stabilizing'}
DETERIORATION = {'weakening', 'distribution', 'failing'}

_regime_cache: dict = {}


async def get_current_regime(db: AsyncSession, today: date) -> str:
    key = today.isoformat()
    if key not in _regime_cache:
        try:
            from app.services.market_regime_engine import MarketRegimeEngine
            engine = MarketRegimeEngine(db)
            analysis = await engine.detect_regime()
            regime_str = analysis.regime.value if hasattr(analysis.regime, 'value') else str(analysis.regime)
        except Exception as e:
            logger.warning(f"Could not detect regime: {e}")
            regime_str = 'unknown'
        _regime_cache.clear()
        _regime_cache[key] = regime_str
    return _regime_cache[key]


class OutcomeTracker:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_observation(
        self,
        symbol: str,
        transition_value: str,
        current_metrics,
        regime: str,
        date_detected: date,
    ) -> None:
        if transition_value == 'stable':
            return
        stmt = (
            insert(TransitionObservation)
            .values(
                symbol=symbol.upper(),
                transition_type=transition_value,
                detected_at=datetime.utcnow(),
                date_detected=date_detected,
                regime_at_detection=regime,
                price_at_detection=getattr(current_metrics, 'current_price', None),
                ema9_at_detection=getattr(current_metrics, 'ema9', None),
                ema21_at_detection=getattr(current_metrics, 'ema21', None),
                ema50_at_detection=getattr(current_metrics, 'ema50', None),
                atr_at_detection=getattr(current_metrics, 'atr', None),
                rs_spy_at_detection=getattr(current_metrics, 'relative_strength_spy', None),
                adr_percent_at_detection=getattr(current_metrics, 'adr_percent', None),
                vcp_score_at_detection=getattr(current_metrics, 'vcp_score', None),
                relative_volume_at_detection=getattr(current_metrics, 'relative_volume', None),
                weekly_tightness_at_detection=getattr(current_metrics, 'weekly_tightness', None),
                outcome_status='PENDING',
            )
            .on_conflict_do_nothing(index_elements=['symbol', 'transition_type', 'date_detected'])
        )
        await self.db.execute(stmt)

    async def evaluate_pending_outcomes(self, as_of_date: date) -> None:
        cutoff_1d = as_of_date - timedelta(days=1)
        q = select(TransitionObservation).where(
            and_(
                TransitionObservation.outcome_status == 'PENDING',
                TransitionObservation.date_detected <= cutoff_1d,
            )
        )
        observations = (await self.db.execute(q)).scalars().all()
        for obs in observations:
            await self._evaluate_one(obs, as_of_date)
        await self.db.commit()
        try:
            from app.services.empirical_probability_calculator import EmpiricalProbabilityCalculator
            EmpiricalProbabilityCalculator.clear_cache()
        except Exception:
            pass

    async def _evaluate_one(self, obs: TransitionObservation, as_of_date: date) -> None:
        end_date = obs.date_detected + timedelta(days=30)
        q = (
            select(StockPrice)
            .where(
                and_(
                    StockPrice.symbol == obs.symbol,
                    StockPrice.date > obs.date_detected,
                    StockPrice.date <= end_date,
                )
            )
            .order_by(StockPrice.date)
        )
        prices = (await self.db.execute(q)).scalars().all()

        if not prices:
            if (as_of_date - obs.date_detected).days >= 15:
                obs.outcome_status = 'INSUFFICIENT_DATA'
                obs.outcome_evaluated_at = datetime.utcnow()
            return

        base = obs.price_at_detection
        atr = obs.atr_at_detection or 0.0

        if len(prices) >= 1 and obs.price_1d is None:
            obs.price_1d = prices[0].close
            obs.pct_1d = (prices[0].close - base) / base * 100 if base else None

        if len(prices) >= 5 and obs.price_5d is None:
            obs.price_5d = prices[4].close
            obs.pct_5d = (prices[4].close - base) / base * 100 if base else None

        if len(prices) >= 20 and obs.price_20d is None:
            obs.price_20d = prices[19].close
            obs.pct_20d = (prices[19].close - base) / base * 100 if base else None

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

            ema21 = obs.ema21_at_detection
            ema50 = obs.ema50_at_detection
            obs.reached_ema21_within_10d = bool(ema21 and max(closes) >= ema21)
            obs.broke_ema50_within_10d = bool(ema50 and min(closes) < ema50)

            obs.outcome_status = self._classify_outcome(obs)
            obs.outcome_evaluated_at = datetime.utcnow()

    def _classify_outcome(self, obs: TransitionObservation) -> str:
        t = obs.transition_type
        dd_atr = obs.max_drawdown_atr_within_10d
        gain_atr = obs.max_gain_atr_within_10d
        pct_5d = obs.pct_5d

        if t in PRE_RECLAIM:
            if obs.broke_ema50_within_10d or (dd_atr is not None and dd_atr < -3.0):
                return 'FAILURE'
            if obs.reached_ema21_within_10d and (dd_atr or 0) > -2.5:
                return 'SUCCESS'
            return 'NEUTRAL'

        if t in BREAKOUT:
            # Breakout (coiling) ya está sobre las EMAs: éxito = el quiebre se
            # materializa (avanza ≥1.5 ATR) sin perder estructura.
            if obs.broke_ema50_within_10d or (dd_atr is not None and dd_atr < -2.0):
                return 'FAILURE'
            if gain_atr is not None and gain_atr >= 1.5 and (dd_atr or 0) > -2.0:
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
            if obs.max_drawdown_within_10d is not None and obs.max_gain_within_10d is not None:
                if obs.max_drawdown_within_10d < -abs(obs.max_gain_within_10d):
                    return 'SUCCESS'
            return 'NEUTRAL'

        return 'NEUTRAL'
