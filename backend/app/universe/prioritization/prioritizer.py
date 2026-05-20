"""
Smart Universe Prioritization

Decide what tickers deserve:
- Realtime WebSocket tracking
- Deep analysis
- Lifecycle tracking
- Setup analysis

Prioritization Factors:
- Institutional quality (market cap, volume, float)
- Leadership (RS, sector leadership)
- Setup quality (pullback quality, tightness)
- Sector relevance (sector in current regime)
- Regime alignment (setup aligned with current regime)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from app.universe.enrichment.enricher import EnrichedTicker
from app.universe.tiers.tier_manager import UniverseTier

logger = logging.getLogger(__name__)


@dataclass
class PriorityScore:
    """Priority score for a ticker"""
    symbol: str
    overall_score: float  # 0-100
    institutional_quality_score: float  # 0-100
    leadership_score: float  # 0-100
    setup_quality_score: float  # 0-100
    sector_relevance_score: float  # 0-100
    regime_alignment_score: float  # 0-100
    recommended_tier: UniverseTier
    requires_realtime: bool
    requires_websocket: bool
    requires_deep_analysis: bool
    requires_setup_analysis: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "overall_score": self.overall_score,
            "institutional_quality_score": self.institutional_quality_score,
            "leadership_score": self.leadership_score,
            "setup_quality_score": self.setup_quality_score,
            "sector_relevance_score": self.sector_relevance_score,
            "regime_alignment_score": self.regime_alignment_score,
            "recommended_tier": self.recommended_tier.value,
            "requires_realtime": self.requires_realtime,
            "requires_websocket": self.requires_websocket,
            "requires_deep_analysis": self.requires_deep_analysis,
            "requires_setup_analysis": self.requires_setup_analysis
        }


class SmartUniversePrioritizer:
    """
    Smart Universe Prioritizer
    
    Decide what tickers deserve:
    - Realtime WebSocket tracking
    - Deep analysis
    - Lifecycle tracking
    - Setup analysis
    
    Prioritization Logic:
    Ticker
      → Calculate institutional quality score (0-100)
      → Calculate leadership score (0-100)
      → Calculate setup quality score (0-100)
      → Calculate sector relevance score (0-100)
      → Calculate regime alignment score (0-100)
      → Overall priority score (weighted average)
      → If score > 80: TIER 1 (full realtime)
      → If score > 60: TIER 2 (partial realtime)
      → If score > 40: TIER 3 (daily)
      → Else: TIER 4 (minimal)
    """
    
    def __init__(self):
        # Weights for overall score calculation
        self.weights = {
            "institutional_quality": 0.30,
            "leadership": 0.25,
            "setup_quality": 0.20,
            "sector_relevance": 0.15,
            "regime_alignment": 0.10
        }
    
    def calculate_priority_score(
        self,
        enriched_ticker: EnrichedTicker,
        market_cap: Optional[float] = None,
        current_regime: Optional[str] = None,
        sector_regime: Optional[Dict[str, str]] = None
    ) -> PriorityScore:
        """
        Calculate priority score for a ticker.
        
        Args:
            enriched_ticker: Enriched ticker information
            market_cap: Market cap
            current_regime: Current market regime
            sector_regime: Dictionary mapping sector to regime alignment
            
        Returns:
            PriorityScore
        """
        # Calculate individual scores
        institutional_quality = self._calculate_institutional_quality_score(enriched_ticker, market_cap)
        leadership = self._calculate_leadership_score(enriched_ticker)
        setup_quality = self._calculate_setup_quality_score(enriched_ticker)
        sector_relevance = self._calculate_sector_relevance_score(enriched_ticker, current_regime, sector_regime)
        regime_alignment = self._calculate_regime_alignment_score(enriched_ticker, current_regime)
        
        # Calculate weighted overall score
        overall_score = (
            institutional_quality * self.weights["institutional_quality"] +
            leadership * self.weights["leadership"] +
            setup_quality * self.weights["setup_quality"] +
            sector_relevance * self.weights["sector_relevance"] +
            regime_alignment * self.weights["regime_alignment"]
        )
        
        # Determine recommended tier and requirements
        recommended_tier, requirements = self._determine_tier_and_requirements(overall_score)
        
        return PriorityScore(
            symbol=enriched_ticker.symbol,
            overall_score=overall_score,
            institutional_quality_score=institutional_quality,
            leadership_score=leadership,
            setup_quality_score=setup_quality,
            sector_relevance_score=sector_relevance,
            regime_alignment_score=regime_alignment,
            recommended_tier=recommended_tier,
            requires_realtime=requirements["realtime"],
            requires_websocket=requirements["websocket"],
            requires_deep_analysis=requirements["deep_analysis"],
            requires_setup_analysis=requirements["setup_analysis"]
        )
    
    def _calculate_institutional_quality_score(self, enriched_ticker: EnrichedTicker, market_cap: Optional[float]) -> float:
        """Calculate institutional quality score (0-100)"""
        score = 50.0  # Base score
        
        # Dollar volume component (0-25 points)
        if enriched_ticker.avg_dollar_volume_20d:
            if enriched_ticker.avg_dollar_volume_20d >= 100_000_000:  # $100M/day
                score += 25
            elif enriched_ticker.avg_dollar_volume_20d >= 10_000_000:  # $10M/day
                score += 20
            elif enriched_ticker.avg_dollar_volume_20d >= 1_000_000:  # $1M/day
                score += 15
            else:
                score += 5
        
        # Float component (0-15 points)
        if enriched_ticker.float_shares and market_cap:
            float_value = enriched_ticker.float_shares * market_cap / enriched_ticker.float_shares
            if float_value >= 1_000_000_000:  # $1B
                score += 15
            elif float_value >= 500_000_000:  # $500M
                score += 12
            elif float_value >= 100_000_000:  # $100M
                score += 8
            else:
                score += 3
        
        # Market cap component (0-10 points)
        if market_cap:
            if market_cap >= 10_000_000_000:  # $10B
                score += 10
            elif market_cap >= 2_000_000_000:  # $2B
                score += 7
            elif market_cap >= 500_000_000:  # $500M
                score += 4
            else:
                score += 1
        
        return max(0, min(100, score))
    
    def _calculate_leadership_score(self, enriched_ticker: EnrichedTicker) -> float:
        """Calculate leadership score (0-100)"""
        score = 50.0  # Base score
        
        # RS component (0-40 points)
        rs_spy = enriched_ticker.rs_baseline_spy or 0
        rs_qqq = enriched_ticker.rs_baseline_qqq or 0
        max_rs = max(rs_spy, rs_qqq)
        
        if max_rs >= 2.0:
            score += 40
        elif max_rs >= 1.5:
            score += 30
        elif max_rs >= 1.2:
            score += 20
        elif max_rs >= 1.0:
            score += 10
        else:
            score -= 10
        
        # Volatility component (0-10 points)
        if enriched_ticker.volatility_profile:
            if enriched_ticker.volatility_profile.value == "low":
                score += 10
            elif enriched_ticker.volatility_profile.value == "moderate":
                score += 7
            elif enriched_ticker.volatility_profile.value == "high":
                score += 3
            else:  # extreme
                score -= 5
        
        return max(0, min(100, score))
    
    def _calculate_setup_quality_score(self, enriched_ticker: EnrichedTicker) -> float:
        """Calculate setup quality score (0-100)"""
        score = 50.0  # Base score
        
        # Tradability component (0-30 points)
        if enriched_ticker.tradability_score:
            score += enriched_ticker.tradability_score * 0.3
        
        # Volatility component (0-20 points)
        if enriched_ticker.atr_percent:
            if enriched_ticker.atr_percent < 2:
                score += 20
            elif enriched_ticker.atr_percent < 5:
                score += 15
            elif enriched_ticker.atr_percent < 10:
                score += 8
            else:
                score -= 5
        
        return max(0, min(100, score))
    
    def _calculate_sector_relevance_score(
        self,
        enriched_ticker: EnrichedTicker,
        current_regime: Optional[str],
        sector_regime: Optional[Dict[str, str]]
    ) -> float:
        """Calculate sector relevance score (0-100)"""
        score = 50.0  # Base score
        
        # If sector is in current regime, boost score
        if enriched_ticker.sector and sector_regime:
            sector_alignment = sector_regime.get(enriched_ticker.sector)
            if sector_alignment == "leading":
                score += 30
            elif sector_alignment == "participating":
                score += 15
            elif sector_alignment == "lagging":
                score -= 10
        
        return max(0, min(100, score))
    
    def _calculate_regime_alignment_score(
        self,
        enriched_ticker: EnrichedTicker,
        current_regime: Optional[str]
    ) -> float:
        """Calculate regime alignment score (0-100)"""
        score = 50.0  # Base score
        
        # If bullish regime and RS > 1, boost score
        if current_regime == "bullish":
            rs_spy = enriched_ticker.rs_baseline_spy or 0
            rs_qqq = enriched_ticker.rs_baseline_qqq or 0
            max_rs = max(rs_spy, rs_qqq)
            
            if max_rs > 1.0:
                score += 30
            elif max_rs > 0.8:
                score += 15
            else:
                score -= 10
        
        return max(0, min(100, score))
    
    def _determine_tier_and_requirements(self, overall_score: float) -> tuple:
        """Determine recommended tier and processing requirements based on score"""
        if overall_score >= 80:
            return UniverseTier.TIER_1, {
                "realtime": True,
                "websocket": True,
                "deep_analysis": True,
                "setup_analysis": True
            }
        elif overall_score >= 60:
            return UniverseTier.TIER_2, {
                "realtime": False,
                "websocket": False,
                "deep_analysis": False,
                "setup_analysis": True
            }
        elif overall_score >= 40:
            return UniverseTier.TIER_3, {
                "realtime": False,
                "websocket": False,
                "deep_analysis": False,
                "setup_analysis": False
            }
        else:
            return UniverseTier.TIER_4, {
                "realtime": False,
                "websocket": False,
                "deep_analysis": False,
                "setup_analysis": False
            }
    
    def prioritize_batch(
        self,
        enriched_tickers: List[EnrichedTicker],
        market_cap_map: Optional[Dict[str, float]] = None,
        current_regime: Optional[str] = None,
        sector_regime: Optional[Dict[str, str]] = None
    ) -> List[PriorityScore]:
        """
        Calculate priority scores for multiple tickers.
        
        Args:
            enriched_tickers: List of enriched tickers
            market_cap_map: Optional mapping of symbol to market cap
            current_regime: Current market regime
            sector_regime: Dictionary mapping sector to regime alignment
            
        Returns:
            List of PriorityScore objects
        """
        scores = []
        
        for ticker in enriched_tickers:
            market_cap = market_cap_map.get(ticker.symbol) if market_cap_map else None
            score = self.calculate_priority_score(ticker, market_cap, current_regime, sector_regime)
            scores.append(score)
        
        # Sort by overall score (descending)
        scores = sorted(scores, key=lambda s: s.overall_score, reverse=True)
        
        logger.info(f"Prioritized {len(scores)} tickers")
        return scores
    
    def get_top_priorities(self, scores: List[PriorityScore], limit: int = 100) -> List[PriorityScore]:
        """
        Get top priority tickers.
        
        Args:
            scores: List of priority scores
            limit: Maximum number to return
            
        Returns:
            List of top priority scores
        """
        return scores[:limit]
    
    def get_prioritization_statistics(self, scores: List[PriorityScore]) -> Dict[str, Any]:
        """
        Get prioritization statistics.
        
        Args:
            scores: List of priority scores
            
        Returns:
            Dictionary with statistics
        """
        if not scores:
            return {"total": 0}
        
        # Average scores
        avg_overall = sum(s.overall_score for s in scores) / len(scores)
        avg_institutional_quality = sum(s.institutional_quality_score for s in scores) / len(scores)
        avg_leadership = sum(s.leadership_score for s in scores) / len(scores)
        avg_setup_quality = sum(s.setup_quality_score for s in scores) / len(scores)
        
        # Count by tier
        tier_counts = {}
        for score in scores:
            tier_counts[s.recommended_tier.value] = tier_counts.get(score.recommended_tier.value, 0) + 1
        
        # Count requirements
        realtime_count = sum(1 for s in scores if s.requires_realtime)
        websocket_count = sum(1 for s in scores if s.requires_websocket)
        deep_analysis_count = sum(1 for s in scores if s.requires_deep_analysis)
        setup_analysis_count = sum(1 for s in scores if s.requires_setup_analysis)
        
        return {
            "total": len(scores),
            "average_overall_score": avg_overall,
            "average_institutional_quality": avg_institutional_quality,
            "average_leadership": avg_leadership,
            "average_setup_quality": avg_setup_quality,
            "tier_distribution": tier_counts,
            "realtime_count": realtime_count,
            "websocket_count": websocket_count,
            "deep_analysis_count": deep_analysis_count,
            "setup_analysis_count": setup_analysis_count
        }
