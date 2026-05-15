"""Service for Quality Swing Setups Scanner"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.models.stock import Stock, StockMetrics
from app.services.sector_mapping import map_sector_to_tradingview


class QualitySwingScannerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_quality_swing_setups(
        self,
        limit: int = 50,
        min_score: float = 60,
        max_distance_ema9: float = 5,
        max_distance_ema21: float = 8,
        max_distance_ath: float = -15
    ):
        """
        Get quality swing setups - stocks meeting institutional swing trading criteria
        
        Criteria:
        - Weekly uptrend intact (weekly_trend_quality >= 0.6)
        - Near ATH (within 15%)
        - Within X% of EMA9/21
        - Volume contraction (volume_contraction > 0.1)
        - Strong weekly structure (weekly_tightness > 0.3)
        - Pullback quality score >= min_score
        - Setup quality in ['excellent', 'good', 'fair']
        - Liquidity (avg_volume_10d >= 700k)
        """
        try:
            result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .where(
                    and_(
                        Stock.is_active == True,
                        StockMetrics.weekly_trend_quality >= 0.6,
                        StockMetrics.distance_to_high_52w >= max_distance_ath,
                        StockMetrics.distance_to_ema9 >= -max_distance_ema9,
                        StockMetrics.distance_to_ema9 <= max_distance_ema9,
                        StockMetrics.distance_to_ema21 >= -max_distance_ema21,
                        StockMetrics.distance_to_ema21 <= max_distance_ema21,
                        StockMetrics.volume_contraction > 0.1,
                        StockMetrics.weekly_tightness > 0.3,
                        StockMetrics.pullback_quality_score >= min_score,
                        StockMetrics.setup_quality.in_(['excellent', 'good', 'fair']),
                        StockMetrics.avg_volume_10d >= 700000
                    )
                )
                .order_by(StockMetrics.pullback_quality_score.desc())
                .limit(limit)
            )
            stocks_with_metrics = result.all()
            
            setups = []
            for stock, metrics in stocks_with_metrics:
                setups.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'sector': map_sector_to_tradingview(stock.sector),
                    'price': metrics.current_price,
                    'pullback_quality_score': metrics.pullback_quality_score,
                    'setup_quality': metrics.setup_quality,
                    'dist_ema9': metrics.distance_to_ema9,
                    'dist_ema21': metrics.distance_to_ema21,
                    'dist_ath': metrics.distance_to_high_52w,
                    'weekly_tightness': metrics.weekly_tightness,
                    'weekly_trend_quality': metrics.weekly_trend_quality,
                    'volume_contraction': metrics.volume_contraction,
                    'weeks_in_base': metrics.weeks_in_base,
                    'rs_spy': metrics.relative_strength_spy,
                    'perf_1w': metrics.perf_1w,
                    'avg_volume_10d': metrics.avg_volume_10d
                })
            
            return setups
        except Exception as e:
            print(f"Error in get_quality_swing_setups: {e}")
            return []
