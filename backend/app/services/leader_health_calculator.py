"""Leader Health Calculator - Measure institutional leader health"""

from dataclasses import dataclass
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


@dataclass
class LeaderHealthMetrics:
    """Complete analysis of institutional leader health"""
    leaders_above_ema21: float  # % of leaders above EMA21
    failed_breakouts: int  # Count of failed breakouts
    distribution_count: int  # Count of stocks in distribution
    pullback_quality_index: float  # Avg pullback quality of leaders
    breakdown_count: int  # Count of EMA50 breakdowns
    reclaim_quality: float  # % of successful reclaim attempts
    continuation_quality: float  # % of successful continuations
    rs_deterioration: int  # Count of leaders with RS deteriorating
    overall_health_score: float  # Aggregate health score (0-1)
    
    def get_summary(self) -> str:
        """Get narrative summary of leader health"""
        return f"Leaders above EMA21: {self.leaders_above_ema21:.0%} | Failed breakouts: {self.failed_breakouts} | Continuation quality: {self.continuation_quality:.0%} | Overall health: {self.overall_health_score:.0%}"


class LeaderHealthCalculator:
    """
    Leader Health Calculator - Measure institutional leader health.
    
    Core philosophy: Measure the health of institutional leadership to
    determine continuation setup viability.
    
    Key indicators:
    - Leaders above EMA21 (%)
    - Failed breakouts (count)
    - Distribution count
    - Pullback quality index
    - Breakdown count
    - Reclaim quality
    - Continuation quality
    - RS deterioration
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_leader_health(self) -> LeaderHealthMetrics:
        """
        Calculate complete leader health analysis.
        
        Returns LeaderHealthMetrics with all indicators.
        """
        leaders_above_ema21 = await self._calculate_leaders_above_ema21()
        failed_breakouts = await self._calculate_failed_breakouts()
        distribution_count = await self._calculate_distribution_count()
        pullback_quality_index = await self._calculate_pullback_quality_index()
        breakdown_count = await self._calculate_breakdown_count()
        reclaim_quality = await self._calculate_reclaim_quality()
        continuation_quality = await self._calculate_continuation_quality()
        rs_deterioration = await self._calculate_rs_deterioration()
        
        # Calculate overall health score
        overall_health_score = self._calculate_overall_health_score(
            leaders_above_ema21,
            failed_breakouts,
            distribution_count,
            pullback_quality_index,
            breakdown_count,
            reclaim_quality,
            continuation_quality
        )
        
        return LeaderHealthMetrics(
            leaders_above_ema21=leaders_above_ema21,
            failed_breakouts=failed_breakouts,
            distribution_count=distribution_count,
            pullback_quality_index=pullback_quality_index,
            breakdown_count=breakdown_count,
            reclaim_quality=reclaim_quality,
            continuation_quality=continuation_quality,
            rs_deterioration=rs_deterioration,
            overall_health_score=overall_health_score
        )
    
    async def _calculate_leaders_above_ema21(self) -> float:
        """
        Calculate % of leaders above EMA21.
        
        Leaders = stocks with pullback_quality_score >= 60
        """
        try:
            # Get total leaders
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.pullback_quality_score >= 60)
            )
            total_leaders = result.scalar() or 0
            
            if total_leaders == 0:
                return 0.0
            
            # Get leaders above EMA21
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.distance_to_ema21 >= 0
                )
            )
            leaders_above = result.scalar() or 0
            
            return leaders_above / total_leaders
            
        except Exception as e:
            logger.error(f"Error calculating leaders above EMA21: {e}")
            return 0.5  # Default neutral
    
    async def _calculate_failed_breakouts(self) -> int:
        """
        Count failed breakouts.
        
        Failed breakout = stock that broke ATH and failed continuation.
        Proxy: distance_to_high_52w < -20% with poor pullback quality.
        """
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.distance_to_high_52w < -20,
                    StockMetrics.pullback_quality_score < 50
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error calculating failed breakouts: {e}")
            return 0
    
    async def _calculate_distribution_count(self) -> int:
        """
        Count stocks in distribution.
        
        Distribution = stocks in WEAKENING/BROKEN state.
        Proxy: distance_to_ema21 < -5% OR distance_to_ema50 < -10%
        """
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    or_(
                        StockMetrics.distance_to_ema21 < -5,
                        StockMetrics.distance_to_ema50 < -10
                    )
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error calculating distribution count: {e}")
            return 0
    
    async def _calculate_pullback_quality_index(self) -> float:
        """
        Calculate average pullback quality of leaders.
        
        Leaders = stocks with pullback_quality_score >= 60
        """
        try:
            result = await self.db.execute(
                select(func.avg(StockMetrics.pullback_quality_score))
                .select_from(StockMetrics)
                .where(StockMetrics.pullback_quality_score >= 60)
            )
            avg_quality = result.scalar()
            
            if avg_quality is None:
                return 50.0  # Default neutral
            
            return avg_quality
            
        except Exception as e:
            logger.error(f"Error calculating pullback quality index: {e}")
            return 50.0
    
    async def _calculate_breakdown_count(self) -> int:
        """
        Count EMA50 breakdowns.
        
        Breakdown = distance_to_ema50 < -10%
        """
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.distance_to_ema50 < -10)
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error calculating breakdown count: {e}")
            return 0
    
    async def _calculate_reclaim_quality(self) -> float:
        """
        Calculate % of successful reclaim attempts.
        
        Proxy: % of leaders near EMA21 with good pullback quality.
        """
        try:
            # Get leaders near EMA21
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.distance_to_ema21 >= -5,
                    StockMetrics.distance_to_ema21 <= 5
                )
            )
            near_ema21 = result.scalar() or 0
            
            if near_ema21 == 0:
                return 0.5  # Default neutral
            
            # Get leaders near EMA21 with good quality
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.distance_to_ema21 >= -5,
                    StockMetrics.distance_to_ema21 <= 5,
                    StockMetrics.pullback_quality_score >= 70
                )
            )
            good_quality = result.scalar() or 0
            
            return good_quality / near_ema21
            
        except Exception as e:
            logger.error(f"Error calculating reclaim quality: {e}")
            return 0.5
    
    async def _calculate_continuation_quality(self) -> float:
        """
        Calculate % of successful continuations.
        
        Proxy: % of leaders holding EMA21 with strong weekly structure.
        """
        try:
            # Get total leaders
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.pullback_quality_score >= 60)
            )
            total_leaders = result.scalar() or 0
            
            if total_leaders == 0:
                return 0.5  # Default neutral
            
            # Get leaders in continuation (holding EMA21 with strong structure)
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.distance_to_ema21 >= 0,
                    StockMetrics.distance_to_ema21 <= 5,
                    StockMetrics.weekly_trend_quality >= 0.7
                )
            )
            continuing = result.scalar() or 0
            
            return continuing / total_leaders
            
        except Exception as e:
            logger.error(f"Error calculating continuation quality: {e}")
            return 0.5
    
    async def _calculate_rs_deterioration(self) -> int:
        """
        Count leaders with RS deteriorating.
        
        Proxy: Leaders with RS < 95
        """
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.relative_strength_spy < 95
                )
            )
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error calculating RS deterioration: {e}")
            return 0
    
    def _calculate_overall_health_score(
        self,
        leaders_above_ema21: float,
        failed_breakouts: int,
        distribution_count: int,
        pullback_quality_index: float,
        breakdown_count: int,
        reclaim_quality: float,
        continuation_quality: float
    ) -> float:
        """
        Calculate aggregate health score (0-1).
        
        Weights:
        - leaders_above_ema21: 25%
        - failed_breakouts (inverse): 15%
        - distribution_count (inverse): 15%
        - pullback_quality_index: 15%
        - breakdown_count (inverse): 10%
        - reclaim_quality: 10%
        - continuation_quality: 10%
        """
        # Get total leaders for normalization
        # This is a simplification - in production would need actual counts
        
        # Normalize failed_breakouts (inverse relationship)
        # Assuming max 50 failed breakouts is bad
        failed_breakouts_score = 1.0 - min(1.0, failed_breakouts / 50.0)
        
        # Normalize distribution_count (inverse relationship)
        # Assuming max 100 distributions is bad
        distribution_score = 1.0 - min(1.0, distribution_count / 100.0)
        
        # Normalize breakdown_count (inverse relationship)
        # Assuming max 50 breakdowns is bad
        breakdown_score = 1.0 - min(1.0, breakdown_count / 50.0)
        
        # Normalize pullback_quality_index (0-100 to 0-1)
        pullback_quality_score = pullback_quality_index / 100.0
        
        # Calculate weighted score
        overall_health = (
            leaders_above_ema21 * 0.25 +
            failed_breakouts_score * 0.15 +
            distribution_score * 0.15 +
            pullback_quality_score * 0.15 +
            breakdown_score * 0.10 +
            reclaim_quality * 0.10 +
            continuation_quality * 0.10
        )
        
        return max(0.0, min(1.0, overall_health))


# Import needed for the _calculate_distribution_count method
from sqlalchemy import or_
