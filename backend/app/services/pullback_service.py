"""Quality Pullbacks Service - Detect institutional-quality pullbacks in strong trends"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Dict, Optional
from app.models.stock import Stock, StockMetrics
from app.services.sector_mapping import map_sector_to_tradingview
# from app.core.redis import redis_client  # DISABLED - Redis not running
import json
import logging

logger = logging.getLogger(__name__)


class PullbackService:
    """Service for detecting quality pullbacks in strong leaders"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_quality_pullbacks(
        self,
        min_score: float = 55,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get quality pullbacks - strong leaders near EMA21

        Criteria:
        - Pullback quality score >= min_score
        - Price within 2% of EMA21 (near optimal pullback zone)
        - Near ATH (within 20%)
        - Strong weekly structure
        - Volume contraction
        - Weekly uptrend intact
        - Price at least 70% above 52-week low (institutional quality)
        - Strong daily trend: price > EMA50 (not below key moving averages)
        - 52-week range >= 60% (current price >= low * 1.6)
        - ADR% > 3% (avoid low volatility stocks)
        """
        try:
            # Try cache first (DISABLED - Redis not running)
            # cache_key = f"quality_pullbacks:{min_score}:{limit}"
            # redis = await redis_client.get_client()
            # cached = await redis.get(cache_key)
            
            # if cached:
            #     logger.info(f"Cache hit for {cache_key}")
            #     return json.loads(cached)
            
            # Use subquery to get only the latest metrics per symbol
            from sqlalchemy import func
            subquery = select(
                StockMetrics.symbol,
                func.max(StockMetrics.date).label('max_date')
            ).group_by(StockMetrics.symbol).subquery()
            
            # Get stocks with metrics (latest date only)
            result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .join(
                    subquery,
                    (StockMetrics.symbol == subquery.c.symbol) &
                    (StockMetrics.date == subquery.c.max_date)
                )
                .where(
                    and_(
                        Stock.is_active == True,
                        StockMetrics.pullback_quality_score >= min_score,
                        StockMetrics.distance_to_ema21 >= -2,  # Within 2% of EMA21 (near optimal pullback zone)
                        StockMetrics.distance_to_high_52w >= -20,  # Within 20% of ATH
                        StockMetrics.weekly_trend_quality >= 0.5,  # Strong weekly trend
                        StockMetrics.setup_quality.in_(['excellent', 'good', 'fair']),
                        StockMetrics.current_price >= StockMetrics.low_52w * 1.7,  # At least 70% above 52-week low
                        StockMetrics.distance_to_ema50 >= 0,  # Price above EMA50 - strong daily trend
                        StockMetrics.low_52w > 0,  # Ensure low_52w exists
                        StockMetrics.high_52w >= StockMetrics.low_52w * 1.6,  # 52-week high >= 60% above low
                        StockMetrics.adr_percent > 3,  # ADR% > 3%
                        StockMetrics.avg_volume_10d >= 700000  # Liquidity filter: avg volume > 700k
                    )
                )
                .order_by(StockMetrics.pullback_quality_score.desc())
                .limit(limit)
            )
            stocks_with_metrics = result.all()
            
            pullbacks = []
            for stock, metrics in stocks_with_metrics:
                pullbacks.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': map_sector_to_tradingview(stock.sector),
                    'price': metrics.current_price,
                    'pullback_quality_score': metrics.pullback_quality_score,
                    'setup_quality': metrics.setup_quality,
                    'dist_ema9': metrics.distance_to_ema9,
                    'dist_ema21': metrics.distance_to_ema21,
                    'dist_ema50': metrics.distance_to_ema50,
                    'dist_ath': metrics.distance_to_high_52w,
                    'weekly_tightness': metrics.weekly_tightness,
                    'weekly_trend_quality': metrics.weekly_trend_quality,
                    'volume_contraction': metrics.volume_contraction,
                    'weeks_in_base': metrics.weeks_in_base,
                    'rs_spy': metrics.relative_strength_spy,
                    'perf_1w': metrics.perf_1w,
                    'perf_4w': metrics.perf_4w,
                    'perf_13w': metrics.perf_13w,
                    'perf_1y': metrics.perf_1y,
                    'avg_volume_10d': metrics.avg_volume_10d,
                    'relative_volume': metrics.relative_volume
                })
            
            logger.info(f"Returning {len(pullbacks)} quality pullbacks")
            return pullbacks
            
        except Exception as e:
            logger.error(f"Error getting quality pullbacks: {e}")
            return []
    
    async def get_leaders_under_pressure(
        self,
        limit: int = 30
    ) -> List[Dict]:
        """
        Get leaders under pressure - structurally strong stocks correcting orderly

        These are stocks that:
        - Have strong weekly structure
        - Are pulling back but maintaining structure
        - Approaching entry zones (EMA9/21)
        - Maintaining relative strength
        - Price at least 70% above 52-week low (institutional quality)
        - Strong daily trend: price > EMA50 (not below key moving averages)
        - 52-week range >= 60% (current price >= low * 1.6)
        - ADR% > 3% (avoid low volatility stocks)
        """
        try:
            result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .where(
                    and_(
                        Stock.is_active == True,
                        StockMetrics.weekly_trend_quality >= 0.6,
                        StockMetrics.distance_to_high_52w >= -15,
                        StockMetrics.perf_1w < 0,  # Currently pulling back
                        StockMetrics.setup_quality.in_(['good', 'fair', 'developing']),
                        StockMetrics.relative_volume < 1.5,  # Not panic selling
                        StockMetrics.current_price >= StockMetrics.low_52w * 1.7,  # At least 70% above 52-week low
                        StockMetrics.distance_to_ema50 >= 0,  # Price above EMA50 - strong daily trend
                        StockMetrics.low_52w > 0,  # Ensure low_52w exists
                        StockMetrics.high_52w >= StockMetrics.low_52w * 1.6,  # 52-week high >= 60% above low
                        StockMetrics.adr_percent > 3,  # ADR% > 3%
                        StockMetrics.avg_volume_10d >= 700000  # Liquidity filter: avg volume > 700k
                    )
                )
                .order_by(StockMetrics.weekly_trend_quality.desc())
                .limit(limit)
            )
            stocks_with_metrics = result.all()
            
            leaders = []
            for stock, metrics in stocks_with_metrics:
                leaders.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': map_sector_to_tradingview(stock.sector),
                    'price': metrics.current_price,
                    'dist_ema9': metrics.distance_to_ema9,
                    'dist_ema21': metrics.distance_to_ema21,
                    'weekly_trend_quality': metrics.weekly_trend_quality,
                    'pullback_quality_score': metrics.pullback_quality_score,
                    'perf_1w': metrics.perf_1w,
                    'volume_contraction': metrics.volume_contraction,
                    'setup_quality': metrics.setup_quality,
                    'rs_spy': metrics.relative_strength_spy
                })
            
            return leaders
            
        except Exception as e:
            logger.error(f"Error getting leaders under pressure: {e}")
            return []
    
    async def get_early_reclaims(
        self,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get early reclaims - stocks that briefly lost EMA9/21 but are reclaiming quickly

        These show:
        - Brief loss of EMA9/21
        - Quick recovery
        - Buying volume entering
        - RS maintained
        - Price at least 70% above 52-week low (institutional quality)
        - Strong daily trend: price > EMA50 (not below key moving averages)
        - 52-week range >= 60% (current price >= low * 1.6)
        - ADR% > 3% (avoid low volatility stocks)
        """
        try:
            result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .where(
                    and_(
                        Stock.is_active == True,
                        StockMetrics.distance_to_ema9 >= -3,  # Recently near EMA9
                        StockMetrics.distance_to_ema9 <= 3,
                        StockMetrics.perf_1w > 0,  # Recovering
                        StockMetrics.relative_volume > 1.2,  # Buying volume
                        StockMetrics.weekly_trend_quality >= 0.5,
                        StockMetrics.current_price >= StockMetrics.low_52w * 1.7,  # At least 70% above 52-week low
                        StockMetrics.distance_to_ema50 >= 0,  # Price above EMA50 - strong daily trend
                        StockMetrics.low_52w > 0,  # Ensure low_52w exists
                        StockMetrics.high_52w >= StockMetrics.low_52w * 1.6,  # 52-week high >= 60% above low
                        StockMetrics.adr_percent > 3,  # ADR% > 3%
                        StockMetrics.avg_volume_10d >= 700000  # Liquidity filter: avg volume > 700k
                    )
                )
                .order_by(StockMetrics.relative_volume.desc())
                .limit(limit)
            )
            stocks_with_metrics = result.all()
            
            reclaims = []
            for stock, metrics in stocks_with_metrics:
                reclaims.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': map_sector_to_tradingview(stock.sector),
                    'price': metrics.current_price,
                    'dist_ema9': metrics.distance_to_ema9,
                    'dist_ema21': metrics.distance_to_ema21,
                    'perf_1w': metrics.perf_1w,
                    'relative_volume': metrics.relative_volume,
                    'weekly_trend_quality': metrics.weekly_trend_quality,
                    'rs_spy': metrics.relative_strength_spy
                })
            
            return reclaims
            
        except Exception as e:
            logger.error(f"Error getting early reclaims: {e}")
            return []
    
    async def get_controlled_pullbacks(
        self,
        limit: int = 30
    ) -> List[Dict]:
        """
        Get controlled pullbacks - differentiate healthy pullbacks from distribution

        HEALTHY pullbacks show:
        - Volume decreasing
        - Small candles
        - Respecting EMA9/21
        - Strong RS
        - Orderly consolidation
        - Price at least 70% above 52-week low (institutional quality)
        - Strong daily trend: price > EMA50 (not below key moving averages)
        - 52-week range >= 60% (current price >= low * 1.6)
        - ADR% > 3% (avoid low volatility stocks)

        UNHEALTHY (distribution) shows:
        - Aggressive selling
        - Breakdown
        - RS deteriorating
        - Selling volume
        """
        try:
            result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .where(
                    and_(
                        Stock.is_active == True,
                        StockMetrics.volume_contraction > 0.2,  # Volume drying up
                        StockMetrics.weekly_tightness > 0.3,  # Tight weekly action
                        StockMetrics.distance_to_ema9 >= -5,
                        StockMetrics.distance_to_ema9 <= 5,
                        StockMetrics.weekly_trend_quality >= 0.5,
                        StockMetrics.setup_quality.in_(['excellent', 'good']),
                        StockMetrics.current_price >= StockMetrics.low_52w * 1.7,  # At least 70% above 52-week low
                        StockMetrics.distance_to_ema50 >= 0,  # Price above EMA50 - strong daily trend
                        StockMetrics.low_52w > 0,  # Ensure low_52w exists
                        StockMetrics.high_52w >= StockMetrics.low_52w * 1.6,  # 52-week high >= 60% above low
                        StockMetrics.adr_percent > 3,  # ADR% > 3%
                        StockMetrics.avg_volume_10d >= 700000  # Liquidity filter: avg volume > 700k
                    )
                )
                .order_by(StockMetrics.volume_contraction.desc())
                .limit(limit)
            )
            stocks_with_metrics = result.all()
            
            controlled = []
            for stock, metrics in stocks_with_metrics:
                controlled.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': map_sector_to_tradingview(stock.sector),
                    'price': metrics.current_price,
                    'dist_ema9': metrics.distance_to_ema9,
                    'dist_ema21': metrics.distance_to_ema21,
                    'volume_contraction': metrics.volume_contraction,
                    'weekly_tightness': metrics.weekly_tightness,
                    'weekly_trend_quality': metrics.weekly_trend_quality,
                    'pullback_quality_score': metrics.pullback_quality_score,
                    'setup_quality': metrics.setup_quality
                })
            
            return controlled
            
        except Exception as e:
            logger.error(f"Error getting controlled pullbacks: {e}")
            return []
