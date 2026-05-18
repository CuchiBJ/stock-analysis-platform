"""Market Regime Engine - Detect market environment for setup context"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime states"""
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    TRANSITION = "transition"
    CHOPPY = "choppy"


@dataclass
class MarketRegimeAnalysis:
    """Complete analysis of current market regime"""
    regime: MarketRegime
    breadth_quality: float
    leadership_health: float
    speculative_appetite: float
    sector_expansion: float
    pullback_environment_quality: float
    confidence: float
    
    def get_summary(self) -> str:
        """Get narrative summary of market regime"""
        return f"Regime: {self.regime.value} | Breadth: {self.breadth_quality:.0%} | Leaders: {self.leadership_health:.0%} | Speculative: {self.speculative_appetite:.0%}"


class MarketRegimeEngine:
    """
    Market Regime Engine - detect market environment for setup context.
    
    Core philosophy: My setups depend heavily on market context.
    Risk ON environments favor continuation setups.
    Risk OFF environments require more defensive posture.
    Transition environments require caution.
    
    Regime detection based on:
    - Breadth quality (advance/decline, new highs/lows)
    - Leadership health (leaders above key moving averages)
    - Speculative appetite (small cap performance, RVOL patterns)
    - Sector expansion (number of strong sectors)
    - Pullback environment quality (how pullbacks are resolving)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def detect_regime(self) -> MarketRegimeAnalysis:
        """
        Detect current market regime.
        
        Returns comprehensive analysis including regime state and
        contributing factors.
        """
        breadth_quality = await self._calculate_breadth_quality()
        leadership_health = await self._calculate_leadership_health()
        speculative_appetite = await self._calculate_speculative_appetite()
        sector_expansion = await self._calculate_sector_expansion()
        pullback_env_quality = await self._calculate_pullback_environment_quality()
        
        # Determine regime based on factors
        regime = self._determine_regime(
            breadth_quality,
            leadership_health,
            speculative_appetite
        )
        
        # Calculate confidence in regime determination
        confidence = self._calculate_confidence(
            breadth_quality,
            leadership_health,
            speculative_appetite
        )
        
        return MarketRegimeAnalysis(
            regime=regime,
            breadth_quality=breadth_quality,
            leadership_health=leadership_health,
            speculative_appetite=speculative_appetite,
            sector_expansion=sector_expansion,
            pullback_environment_quality=pullback_env_quality,
            confidence=confidence
        )
    
    async def _calculate_breadth_quality(self) -> float:
        """
        Calculate breadth quality (0-1).
        
        Based on:
        - Percentage of stocks above EMA50
        - Percentage of stocks making new highs vs new lows
        - Advance/decline ratio
        """
        try:
            # Get percentage of stocks above EMA50
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.distance_to_ema50 >= 0)
            )
            above_ema50 = result.scalar() or 0
            
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
            )
            total = result.scalar() or 1
            
            breadth_quality = above_ema50 / total if total > 0 else 0.5
            
            # Adjust based on distance to high (more stocks near highs = better breadth)
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.distance_to_high_52w >= -10)
            )
            near_highs = result.scalar() or 0
            
            near_highs_ratio = near_highs / total if total > 0 else 0.5
            
            # Combine factors
            breadth_quality = (breadth_quality * 0.7) + (near_highs_ratio * 0.3)
            
            return min(1.0, max(0.0, breadth_quality))
            
        except Exception as e:
            logger.error(f"Error calculating breadth quality: {e}")
            return 0.5  # Default to neutral
    
    async def _calculate_leadership_health(self) -> float:
        """
        Calculate leadership health (0-1).
        
        Based on:
        - Percentage of institutional leaders above EMA21
        - Percentage of leaders with strong RS
        - Breakdown count vs reclaim count
        """
        try:
            # Get stocks with high pullback quality score (leaders)
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.pullback_quality_score >= 60)
            )
            leaders = result.scalar() or 0
            
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
            )
            total = result.scalar() or 1
            
            if total == 0:
                return 0.5
            
            # Get percentage of leaders above EMA21
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.distance_to_ema21 >= 0
                )
            )
            leaders_above_ema21 = result.scalar() or 0
            
            if leaders == 0:
                return 0.5
            
            leadership_health = leaders_above_ema21 / leaders
            
            # Adjust based on RS quality
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(
                    StockMetrics.pullback_quality_score >= 60,
                    StockMetrics.relative_strength_spy >= 105
                )
            )
            strong_rs_leaders = result.scalar() or 0
            
            rs_quality = strong_rs_leaders / leaders if leaders > 0 else 0.5
            
            # Combine factors
            leadership_health = (leadership_health * 0.7) + (rs_quality * 0.3)
            
            return min(1.0, max(0.0, leadership_health))
            
        except Exception as e:
            logger.error(f"Error calculating leadership health: {e}")
            return 0.5  # Default to neutral
    
    async def _calculate_speculative_appetite(self) -> float:
        """
        Calculate speculative appetite (0-1).
        
        Based on:
        - Small cap performance vs large cap
        - RVOL patterns
        - Recent volatility
        """
        try:
            # Simplified version - use ADR as proxy for speculative appetite
            result = await self.db.execute(
                select(func.avg(StockMetrics.adr_percent))
                .select_from(StockMetrics)
                .where(StockMetrics.adr_percent.isnot(None))
            )
            avg_adr = result.scalar() or 3.0
            
            # Higher ADR = higher speculative appetite
            # Normalize: 3% = 0.5 (neutral), 5%+ = 1.0 (high), 1% = 0.0 (low)
            speculative_appetite = (avg_adr - 1.0) / 4.0
            
            return min(1.0, max(0.0, speculative_appetite))
            
        except Exception as e:
            logger.error(f"Error calculating speculative appetite: {e}")
            return 0.5  # Default to neutral
    
    async def _calculate_sector_expansion(self) -> float:
        """
        Calculate sector expansion (0-1).
        
        Based on:
        - Number of sectors with strong performance
        - Sector breadth
        """
        try:
            # Simplified version - use percentage of stocks with positive weekly performance
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
                .where(StockMetrics.perf_1w > 0)
            )
            positive_weekly = result.scalar() or 0
            
            result = await self.db.execute(
                select(func.count())
                .select_from(StockMetrics)
            )
            total = result.scalar() or 1
            
            sector_expansion = positive_weekly / total if total > 0 else 0.5
            
            return min(1.0, max(0.0, sector_expansion))
            
        except Exception as e:
            logger.error(f"Error calculating sector expansion: {e}")
            return 0.5  # Default to neutral
    
    async def _calculate_pullback_environment_quality(self) -> float:
        """
        Calculate pullback environment quality (0-1).
        
        Based on:
        - How pullbacks are resolving (reclaim vs breakdown)
        - Average pullback quality score
        """
        try:
            # Get average pullback quality score
            result = await self.db.execute(
                select(func.avg(StockMetrics.pullback_quality_score))
                .select_from(StockMetrics)
                .where(StockMetrics.pullback_quality_score.isnot(None))
            )
            avg_pullback_quality = result.scalar() or 50.0
            
            # Normalize to 0-1
            pullback_env_quality = avg_pullback_quality / 100.0
            
            return min(1.0, max(0.0, pullback_env_quality))
            
        except Exception as e:
            logger.error(f"Error calculating pullback environment quality: {e}")
            return 0.5  # Default to neutral
    
    def _determine_regime(
        self,
        breadth_quality: float,
        leadership_health: float,
        speculative_appetite: float
    ) -> MarketRegime:
        """
        Determine market regime based on factors.
        
        Rule-based detection for interpretability.
        """
        # Risk ON: Strong breadth + healthy leadership
        if breadth_quality > 0.65 and leadership_health > 0.65:
            return MarketRegime.RISK_ON
        
        # Risk OFF: Weak breadth + poor leadership
        if breadth_quality < 0.40 or leadership_health < 0.40:
            return MarketRegime.RISK_OFF
        
        # Transition: Mixed signals
        if abs(breadth_quality - leadership_health) > 0.2:
            return MarketRegime.TRANSITION
        
        # Choppy: Neutral breadth + neutral leadership
        return MarketRegime.CHOPPY
    
    def _calculate_confidence(
        self,
        breadth_quality: float,
        leadership_health: float,
        speculative_appetite: float
    ) -> float:
        """
        Calculate confidence in regime determination (0-1).
        
        Higher confidence when factors are aligned.
        """
        # Calculate standard deviation of factors
        factors = [breadth_quality, leadership_health, speculative_appetite]
        mean = sum(factors) / len(factors)
        variance = sum((x - mean) ** 2 for x in factors) / len(factors)
        std_dev = variance ** 0.5
        
        # Lower std dev = higher confidence
        confidence = 1.0 - min(1.0, std_dev)
        
        return max(0.5, confidence)  # Minimum 50% confidence
