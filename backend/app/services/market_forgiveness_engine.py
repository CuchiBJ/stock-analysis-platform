"""Market Forgiveness Model - Measure how market responds to failed setups"""

from enum import Enum
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.stock import StockMetrics
from app.services.setup_lifecycle_engine import SetupState
import logging

logger = logging.getLogger(__name__)


class ForgivenessLevel(Enum):
    """Level of market forgiveness for failed setups"""
    HIGH = "high"           # Market quickly forgives failures (good for re-entry)
    MODERATE = "moderate"   # Market moderately forgives failures
    LOW = "low"             # Market does not forgive failures (avoid re-entry)
    VERY_LOW = "very_low"   # Market severely punishes failures (stay away)


@dataclass
class ForgivenessMetrics:
    """Metrics for market forgiveness of a failed setup"""
    symbol: str
    forgiveness_level: ForgivenessLevel
    recovery_speed: float  # Days to recover after failure
    recovery_magnitude: float  # Percentage recovered
    volume_during_recovery: float  # Volume pattern during recovery
    support_level_strength: float  # Strength of support level
    market_regime_at_failure: str
    forgiveness_score: float  # 0-1 composite score


class MarketForgivenessEngine:
    """
    Market Forgiveness Model - Measure how market responds to failed setups.
    
    Core philosophy: Not all failed setups are equal. Some setups fail but
    the market quickly forgives and the stock recovers. Others fail and the
    market severely punishes the stock. Understanding market forgiveness is
    crucial for re-entry decisions and risk management.
    
    Expected outcome:
    - Measure how quickly and strongly the market forgives failed setups
    - Identify setups that are good re-entry candidates after failure
    - Detect setups that should be avoided after failure
    - Understand market regime impact on forgiveness patterns
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def calculate_forgiveness_metrics(
        self,
        symbol: str,
        failure_state: SetupState,
        current_metrics: StockMetrics
    ) -> ForgivenessMetrics:
        """
        Calculate forgiveness metrics for a failed setup.
        
        Args:
            symbol: Stock symbol
            failure_state: State when setup failed
            current_metrics: Current stock metrics
        
        Returns:
            ForgivenessMetrics with forgiveness level and score
        """
        # Calculate recovery speed (simulated - would need historical data)
        recovery_speed = self._estimate_recovery_speed(current_metrics)
        
        # Calculate recovery magnitude
        recovery_magnitude = self._estimate_recovery_magnitude(current_metrics)
        
        # Calculate volume pattern during recovery
        volume_during_recovery = self._analyze_recovery_volume(current_metrics)
        
        # Calculate support level strength
        support_level_strength = self._calculate_support_strength(current_metrics)
        
        # Determine forgiveness level
        forgiveness_level = self._determine_forgiveness_level(
            recovery_speed,
            recovery_magnitude,
            volume_during_recovery,
            support_level_strength
        )
        
        # Calculate composite forgiveness score
        forgiveness_score = self._calculate_forgiveness_score(
            recovery_speed,
            recovery_magnitude,
            volume_during_recovery,
            support_level_strength
        )
        
        return ForgivenessMetrics(
            symbol=symbol,
            forgiveness_level=forgiveness_level,
            recovery_speed=recovery_speed,
            recovery_magnitude=recovery_magnitude,
            volume_during_recovery=volume_during_recovery,
            support_level_strength=support_level_strength,
            market_regime_at_failure="unknown",  # Would need historical data
            forgiveness_score=forgiveness_score
        )
    
    def is_good_reentry_candidate(
        self,
        forgiveness_metrics: ForgivenessMetrics
    ) -> Tuple[bool, str]:
        """
        Determine if a failed setup is a good re-entry candidate.
        
        Returns tuple of (is_candidate, rationale)
        """
        if forgiveness_metrics.forgiveness_level in [ForgivenessLevel.HIGH, ForgivenessLevel.MODERATE]:
            if forgiveness_metrics.forgiveness_score > 0.6:
                return True, (
                    f"Market forgiveness is {forgiveness_metrics.forgiveness_level.value}. "
                    f"Forgiveness score: {forgiveness_metrics.forgiveness_score:.2f}. "
                    f"Good re-entry candidate."
                )
        
        return False, (
            f"Market forgiveness is {forgiveness_metrics.forgiveness_level.value}. "
            f"Forgiveness score: {forgiveness_metrics.forgiveness_score:.2f}. "
            f"Not a good re-entry candidate."
        )
    
    def analyze_sector_forgiveness(
        self,
        sector: str
    ) -> Dict:
        """
        Analyze market forgiveness patterns for a sector.
        
        Returns aggregated forgiveness metrics for the sector.
        """
        # This would require sector data and historical analysis
        # For now, return placeholder
        return {
            "sector": sector,
            "avg_forgiveness_score": 0.5,
            "high_forgiveness_count": 0,
            "moderate_forgiveness_count": 0,
            "low_forgiveness_count": 0,
            "avg_recovery_speed": 0.0,
            "avg_recovery_magnitude": 0.0
        }
    
    def get_forgiveness_by_market_regime(
        self,
        market_regime: str
    ) -> Dict:
        """
        Get market forgiveness patterns by market regime.
        
        Returns forgiveness statistics for different market regimes.
        """
        # This would require historical data analysis
        # For now, return placeholder based on regime
        regime_forgiveness = {
            "strong_bullish": {
                "avg_forgiveness_score": 0.8,
                "high_forgiveness_percentage": 70,
                "description": "Market strongly forgives failures in bullish regimes"
            },
            "bullish": {
                "avg_forgiveness_score": 0.7,
                "high_forgiveness_percentage": 60,
                "description": "Market moderately forgives failures in bullish regimes"
            },
            "choppy": {
                "avg_forgiveness_score": 0.5,
                "high_forgiveness_percentage": 40,
                "description": "Market forgiveness is neutral in choppy regimes"
            },
            "bearish": {
                "avg_forgiveness_score": 0.3,
                "high_forgiveness_percentage": 20,
                "description": "Market does not forgive failures in bearish regimes"
            },
            "strong_bearish": {
                "avg_forgiveness_score": 0.2,
                "high_forgiveness_percentage": 10,
                "description": "Market severely punishes failures in bearish regimes"
            }
        }
        
        return regime_forgiveness.get(market_regime, regime_forgiveness["choppy"])
    
    # --- Helper methods ---
    
    def _estimate_recovery_speed(self, metrics: StockMetrics) -> float:
        """
        Estimate recovery speed in days (simulated).
        
        Based on:
        - Distance to EMA21 (closer = faster recovery)
        - Weekly trend quality (higher = faster recovery)
        - Volume pattern (supportive = faster recovery)
        """
        speed_score = 0.0
        
        # EMA21 distance contribution
        if metrics.distance_to_ema21 is not None:
            # Closer to EMA21 = faster recovery
            distance_score = max(0, 1 - abs(metrics.distance_to_ema21) / 15.0)
            speed_score += distance_score * 0.4
        
        # Weekly trend contribution
        if metrics.weekly_trend_quality:
            speed_score += metrics.weekly_trend_quality * 0.3
        
        # Volume pattern contribution
        if metrics.volume_contraction:
            # Moderate contraction = good recovery
            if 0.3 <= metrics.volume_contraction <= 0.7:
                speed_score += 0.3
            elif metrics.volume_contraction > 0.7:
                speed_score += 0.2
            else:
                speed_score += 0.1
        
        # Convert to estimated days (0-30 days)
        estimated_days = (1 - speed_score) * 30
        return max(1.0, min(30.0, estimated_days))
    
    def _estimate_recovery_magnitude(self, metrics: StockMetrics) -> float:
        """
        Estimate recovery magnitude as percentage (simulated).
        
        Based on:
        - Pullback quality score
        - Distance from low
        - Support level strength
        """
        magnitude_score = 0.0
        
        # Pullback quality contribution
        if metrics.pullback_quality_score:
            magnitude_score += (metrics.pullback_quality_score / 100.0) * 0.4
        
        # Distance from 52-week low contribution
        if metrics.distance_to_high_52w is not None:
            # Not too far from highs = better recovery
            distance_score = max(0, 1 + metrics.distance_to_high_52w / 50.0)
            magnitude_score += distance_score * 0.3
        
        # Weekly structure contribution
        if metrics.weeks_in_base:
            # Longer base = stronger recovery
            base_score = min(1.0, metrics.weeks_in_base / 10.0)
            magnitude_score += base_score * 0.3
        
        # Convert to percentage (0-50%)
        recovery_pct = magnitude_score * 50
        return max(0.0, min(50.0, recovery_pct))
    
    def _analyze_recovery_volume(self, metrics: StockMetrics) -> float:
        """
        Analyze volume pattern during recovery (0-1 score).
        
        High score = supportive volume pattern
        Low score = distributive or drying up volume
        """
        volume_score = 0.5  # Base score
        
        if metrics.volume_contraction:
            # Moderate contraction is good
            if 0.3 <= metrics.volume_contraction <= 0.7:
                volume_score = 0.8
            # High contraction is okay
            elif metrics.volume_contraction > 0.7:
                volume_score = 0.7
            # Low contraction is concerning
            else:
                volume_score = 0.4
        
        if metrics.avg_volume_10d:
            # Sufficient volume is good
            if metrics.avg_volume_10d >= 1000000:  # 1M+
                volume_score += 0.1
            elif metrics.avg_volume_10d >= 500000:  # 500k+
                volume_score += 0.05
            else:
                volume_score -= 0.1
        
        return max(0.0, min(1.0, volume_score))
    
    def _calculate_support_strength(self, metrics: StockMetrics) -> float:
        """
        Calculate support level strength (0-1 score).
        
        Based on:
        - EMA50 support
        - Weekly structure
        - Previous consolidation levels
        """
        support_score = 0.0
        
        # EMA50 support
        if metrics.distance_to_ema50 is not None:
            # Close to EMA50 = strong support
            if abs(metrics.distance_to_ema50) <= 5:
                support_score += 0.4
            elif abs(metrics.distance_to_ema50) <= 10:
                support_score += 0.3
            else:
                support_score += 0.1
        
        # Weekly structure support
        if metrics.weeks_in_base:
            # Longer base = stronger support
            base_score = min(1.0, metrics.weeks_in_base / 8.0)
            support_score += base_score * 0.3
        
        # Weekly tightness support
        if metrics.weekly_tightness:
            support_score += metrics.weekly_tightness * 0.3
        
        return max(0.0, min(1.0, support_score))
    
    def _determine_forgiveness_level(
        self,
        recovery_speed: float,
        recovery_magnitude: float,
        volume_during_recovery: float,
        support_level_strength: float
    ) -> ForgivenessLevel:
        """Determine forgiveness level based on metrics"""
        # Calculate composite score
        score = self._calculate_forgiveness_score(
            recovery_speed,
            recovery_magnitude,
            volume_during_recovery,
            support_level_strength
        )
        
        if score >= 0.8:
            return ForgivenessLevel.HIGH
        elif score >= 0.6:
            return ForgivenessLevel.MODERATE
        elif score >= 0.4:
            return ForgivenessLevel.LOW
        else:
            return ForgivenessLevel.VERY_LOW
    
    def _calculate_forgiveness_score(
        self,
        recovery_speed: float,
        recovery_magnitude: float,
        volume_during_recovery: float,
        support_level_strength: float
    ) -> float:
        """
        Calculate composite forgiveness score (0-1).
        
        Weights:
        - Recovery speed (40%): Faster = higher score
        - Recovery magnitude (30%): Higher = higher score
        - Volume pattern (20%): Supportive = higher score
        - Support strength (10%): Stronger = higher score
        """
        # Normalize recovery speed (0-30 days) to 0-1 (inverted: faster = higher)
        speed_score = max(0, 1 - recovery_speed / 30.0)
        
        # Normalize recovery magnitude (0-50%) to 0-1
        magnitude_score = recovery_magnitude / 50.0
        
        # Composite score
        composite_score = (
            speed_score * 0.4 +
            magnitude_score * 0.3 +
            volume_during_recovery * 0.2 +
            support_level_strength * 0.1
        )
        
        return max(0.0, min(1.0, composite_score))
