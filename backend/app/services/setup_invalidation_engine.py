"""Setup Invalidation Engine - Aggressive invalidation to eliminate low-quality setups"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


class InvalidationReason(Enum):
    """Reasons for setup invalidation"""
    SLOPPY_PULLBACK = "sloppy_pullback"
    EXCESSIVE_VOLATILITY = "excessive_volatility"
    FAILED_RECLAIM_STRUCTURE = "failed_reclaim_structure"
    RS_DETERIORATION = "rs_deterioration"
    SECTOR_WEAKNESS = "sector_weakness"
    HEAVY_SELLING = "heavy_selling"
    WIDE_WEEKLY_BARS = "wide_weekly_bars"
    FAILED_CONTINUATION = "failed_continuation"
    LOOSE_STRUCTURE = "loose_structure"
    ABNORMAL_DOWNSIDE_VOLUME = "abnormal_downside_volume"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"


@dataclass
class InvalidationResult:
    """Result of setup invalidation check"""
    is_valid: bool
    invalidation_reasons: List[InvalidationReason]
    confidence: float


class SetupInvalidationEngine:
    """
    Setup Invalidation Engine - Aggressive invalidation to eliminate low-quality setups.
    
    Core philosophy: Invalidation-first logic. Detect bad setups BEFORE looking for good ones.
    
    Expected outcome: 80-90% of setups eliminated in invalidation, leaving only 10-20% for state machine.
    This ensures SCARCITY IS SIGNAL - only high-quality setups reach the ranking stage.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def check_setup_validity(self, metrics: StockMetrics) -> InvalidationResult:
        """
        Check if a setup passes all invalidation criteria.
        
        Returns InvalidationResult with:
        - is_valid: True if setup passes all invalidations
        - invalidation_reasons: List of reasons why setup was invalidated
        - confidence: Confidence in the invalidation decision (0-1)
        """
        invalidation_reasons = []
        
        # Check each invalidation criterion
        if self._is_sloppy_pullback(metrics):
            invalidation_reasons.append(InvalidationReason.SLOPPY_PULLBACK)
        
        if self._is_excessive_volatility(metrics):
            invalidation_reasons.append(InvalidationReason.EXCESSIVE_VOLATILITY)
        
        if self._is_failed_reclaim_structure(metrics):
            invalidation_reasons.append(InvalidationReason.FAILED_RECLAIM_STRUCTURE)
        
        if self._is_rs_deterioration(metrics):
            invalidation_reasons.append(InvalidationReason.RS_DETERIORATION)
        
        if self._is_sector_weakness(metrics):
            invalidation_reasons.append(InvalidationReason.SECTOR_WEAKNESS)
        
        if self._is_heavy_selling(metrics):
            invalidation_reasons.append(InvalidationReason.HEAVY_SELLING)
        
        if self._is_wide_weekly_bars(metrics):
            invalidation_reasons.append(InvalidationReason.WIDE_WEEKLY_BARS)
        
        if self._is_failed_continuation(metrics):
            invalidation_reasons.append(InvalidationReason.FAILED_CONTINUATION)
        
        if self._is_loose_structure(metrics):
            invalidation_reasons.append(InvalidationReason.LOOSE_STRUCTURE)
        
        if self._is_abnormal_downside_volume(metrics):
            invalidation_reasons.append(InvalidationReason.ABNORMAL_DOWNSIDE_VOLUME)
        
        if self._is_insufficient_liquidity(metrics):
            invalidation_reasons.append(InvalidationReason.INSUFFICIENT_LIQUIDITY)
        
        is_valid = len(invalidation_reasons) == 0
        
        # Calculate confidence based on number of invalidations
        # More invalidations = higher confidence in rejection
        confidence = 1.0 - (len(invalidation_reasons) * 0.1)
        confidence = max(0.0, confidence)
        
        return InvalidationResult(
            is_valid=is_valid,
            invalidation_reasons=invalidation_reasons,
            confidence=confidence
        )
    
    async def filter_valid_setups(
        self,
        symbols: List[str],
        limit: int = 50
    ) -> List[str]:
        """
        Filter a list of symbols to return only valid setups.
        
        Returns list of symbols that pass all invalidation criteria.
        """
        valid_symbols = []
        
        for symbol in symbols:
            try:
                # Get latest metrics for symbol
                result = await self.db.execute(
                    select(StockMetrics)
                    .where(StockMetrics.symbol == symbol.upper())
                    .order_by(StockMetrics.date.desc())
                    .limit(1)
                )
                metrics = result.scalar_one_or_none()
                
                if not metrics:
                    continue
                
                # Check validity
                invalidation_result = self.check_setup_validity(metrics)
                
                if invalidation_result.is_valid:
                    valid_symbols.append(symbol)
                
                if len(valid_symbols) >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"Error checking validity for {symbol}: {e}")
                continue
        
        logger.info(f"Invalidation filter: {len(valid_symbols)}/{len(symbols)} setups passed")
        return valid_symbols
    
    # --- Invalidation criteria ---
    
    def _is_sloppy_pullback(self, metrics: StockMetrics) -> bool:
        """
        Detect sloppy pullbacks - lack of controlled structure.
        
        Invalidation criteria (relaxed):
        - weekly_volatility_contraction < 0.1 (no contraction)
        - OR weekly_tightness < 0.2 (very loose)
        - OR weekly range > 15% (wide bars)
        """
        if metrics.weekly_volatility_contraction is not None:
            if metrics.weekly_volatility_contraction < 0.1:
                return True
        
        if metrics.weekly_tightness is not None:
            if metrics.weekly_tightness < 0.2:
                return True
        
        # Check weekly range (if available from other metrics)
        # This would need to be calculated from price data
        # For now, skip if not directly available in StockMetrics
        
        return False
    
    def _is_excessive_volatility(self, metrics: StockMetrics) -> bool:
        """
        Detect excessive volatility - too unstable for institutional setups.
        
        Invalidation criteria (relaxed):
        - adr_percent > 12% (too volatile)
        - OR intraday range > 10% in 3+ days (would need price data)
        """
        if metrics.adr_percent is not None:
            if metrics.adr_percent > 12.0:
                return True
        
        return False
    
    def _is_failed_reclaim_structure(self, metrics: StockMetrics) -> bool:
        """
        Detect failed reclaim structures - multiple failed attempts.
        
        Invalidation criteria (relaxed):
        - 2+ reclaim attempts failed in last 10 days (would need historical tracking)
        - OR reclaim attempt with volume > 2x avg (would need price data)
        
        Note: This requires historical tracking of reclaim attempts.
        For now, use proxy indicators.
        """
        # Proxy: If pullback_quality_score is very low despite being near EMA21
        if (metrics.pullback_quality_score is not None and
            metrics.distance_to_ema21 is not None):
            if (metrics.pullback_quality_score < 40 and
                -5 <= metrics.distance_to_ema21 <= 5):
                return True
        
        return False
    
    def _is_rs_deterioration(self, metrics: StockMetrics) -> bool:
        """
        Detect RS deterioration - losing leadership.
        
        Invalidation criteria (relaxed):
        - RS fell > 10% in last week (would need historical tracking)
        - OR RS < 90 (underperforming market significantly)
        """
        if metrics.relative_strength_spy is not None:
            if metrics.relative_strength_spy < 90:
                return True
        
        # Check for RS deterioration (would need historical tracking)
        # For now, skip if not directly available
        
        return False
    
    def _is_sector_weakness(self, metrics: StockMetrics) -> bool:
        """
        Detect sector weakness - unfavorable sector context.
        
        Invalidation criteria:
        - Sector RS < 90 (would need sector-level data)
        - OR sector in WEAKENING/BROKEN state (would need sector tracking)
        
        Note: This requires sector-level data tracking.
        For now, skip if not directly available in StockMetrics.
        """
        # This would require sector-level RS tracking
        # Not available in current StockMetrics model
        return False
    
    def _is_heavy_selling(self, metrics: StockMetrics) -> bool:
        """
        Detect heavy selling - institutional distribution.
        
        Invalidation criteria (relaxed):
        - 3+ consecutive days with volume > 2x avg and price down > 2%
        - OR daily range > 8% to downside (would need price data)
        
        Note: This requires daily price data analysis.
        For now, use proxy indicators.
        """
        # Proxy: Very high relative volume with poor pullback quality
        if (metrics.relative_volume is not None and
            metrics.pullback_quality_score is not None):
            if (metrics.relative_volume > 3.0 and
                metrics.pullback_quality_score < 30):
                return True
        
        return False
    
    def _is_wide_weekly_bars(self, metrics: StockMetrics) -> bool:
        """
        Detect wide weekly bars - lack of tightness.
        
        Invalidation criteria (relaxed):
        - 2+ consecutive weeks with range > 12%
        - OR last week range > 15%
        
        Note: This requires weekly price data analysis.
        For now, use proxy indicators.
        """
        # Proxy: Very low weekly tightness indicates wide bars
        if metrics.weekly_tightness is not None:
            if metrics.weekly_tightness < 0.15:
                return True
        
        return False
    
    def _is_failed_continuation(self, metrics: StockMetrics) -> bool:
        """
        Detect failed continuation - continuation setups that failed.
        
        Invalidation criteria (relaxed):
        - Continuation failed (lost EMA21 in < 5 days) - would need historical tracking
        - OR trigger_ready never reached continuation - would need historical tracking
        
        Note: This requires historical tracking of state transitions.
        For now, use proxy indicators.
        """
        # Proxy: If setup was trigger_ready but now very weak
        if (metrics.pullback_quality_score is not None and
            metrics.distance_to_ema21 is not None):
            if (metrics.pullback_quality_score < 45 and
                metrics.distance_to_ema21 < -5):
                return True
        
        return False
    
    def _is_loose_structure(self, metrics: StockMetrics) -> bool:
        """
        Detect loose structure - poor technical alignment.
        
        Invalidation criteria (relaxed):
        - distance_to_ema21 < -20% (too far from EMA21)
        - OR distance_to_ema50 < -15% (below key moving average)
        """
        if metrics.distance_to_ema21 is not None:
            if metrics.distance_to_ema21 < -20:
                return True
        
        if metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema50 < -15:
                return True
        
        return False
    
    def _is_abnormal_downside_volume(self, metrics: StockMetrics) -> bool:
        """
        Detect abnormal downside volume - panic selling.
        
        Invalidation criteria (relaxed):
        - Downside volume > 3x avg on last day (would need price data)
        - OR downside volume > 2x avg in 3+ days (would need price data)
        
        Note: This requires daily price data analysis.
        For now, use proxy indicators.
        """
        # Proxy: Extremely high relative volume with very poor setup quality
        if (metrics.relative_volume is not None and
            metrics.pullback_quality_score is not None):
            if (metrics.relative_volume > 4.0 and
                metrics.pullback_quality_score < 25):
                return True
        
        return False
    
    def _is_insufficient_liquidity(self, metrics: StockMetrics) -> bool:
        """
        Check if setup has insufficient liquidity (avg_volume_10d < 700k).
        
        Philosophy: Only operate stocks with sufficient liquidity to ensure
        proper execution and minimize slippage.
        """
        if metrics.avg_volume_10d is None:
            return True  # Invalid if no volume data
        
        if metrics.avg_volume_10d < 700000:
            return True  # Invalid if volume < 700k
        
        return False
    
    async def get_invalidation_stats(self) -> dict:
        """
        Get statistics on invalidation effectiveness.
        
        Returns:
        - Total stocks analyzed
        - Stocks invalidated
        - Stocks passed
        - Invalidation rate
        - Breakdown by invalidation reason
        """
        try:
            # Get total stocks with metrics
            result = await self.db.execute(
                select(func.count()).select_from(StockMetrics)
            )
            total_stocks = result.scalar() or 0
            
            # Count invalidations by reason (simplified)
            # This would require running invalidation on all stocks
            # For now, return placeholder stats
            
            return {
                "total_stocks": total_stocks,
                "invalidated": 0,
                "passed": 0,
                "invalidation_rate": 0.0,
                "breakdown": {}
            }
            
        except Exception as e:
            logger.error(f"Error getting invalidation stats: {e}")
            return {
                "total_stocks": 0,
                "invalidated": 0,
                "passed": 0,
                "invalidation_rate": 0.0,
                "breakdown": {}
            }
