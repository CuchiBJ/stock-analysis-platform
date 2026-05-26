"""Setup Priority Engine - Rank setups by priority_score, show only top 3-6"""

from dataclasses import dataclass
from typing import List, Optional
from app.models.stock import StockMetrics
from app.services.setup_lifecycle_engine import SetupState
from app.services.contextual_setup_engine import ContextualSetupEngine
import logging

logger = logging.getLogger(__name__)


@dataclass
class SetupPriority:
    """Priority score and breakdown for a setup"""
    symbol: str
    priority_score: float
    state_quality: float
    transition_strength: float
    weekly_structure: float
    rs_stability: float
    regime_alignment: float
    pullback_quality: float
    current_state: SetupState
    
    def get_breakdown(self) -> dict:
        """Get detailed breakdown of priority score"""
        return {
            "symbol": self.symbol,
            "priority_score": self.priority_score,
            "state_quality": self.state_quality,
            "transition_strength": self.transition_strength,
            "weekly_structure": self.weekly_structure,
            "rs_stability": self.rs_stability,
            "regime_alignment": self.regime_alignment,
            "pullback_quality": self.pullback_quality,
            "current_state": self.current_state.value
        }


class SetupPriorityEngine:
    """
    Setup Priority Engine - Rank setups by priority_score, show only top 3-6.
    
    Core philosophy: When multiple valid setups exist, the system must decide
    WHICH setups deserve attention NOW.
    
    Priority scoring based on:
    - state_quality (30%)
    - transition_strength (25%)
    - weekly_structure (15%)
    - rs_stability (10%)
    - regime_alignment (10%)
    - pullback_quality (10%)
    
    Expected outcome: Show only top 3-6 setups ranked by priority_score.
    Filter by priority_score >= 70 to ensure quality threshold.
    """
    
    def __init__(self):
        self.contextual_engine = ContextualSetupEngine()
    
    def calculate_priority_score(
        self,
        metrics: StockMetrics,
        current_state: SetupState,
        market_regime: Optional[str] = None
    ) -> SetupPriority:
        """
        Calculate priority score for a setup.
        
        Returns SetupPriority with detailed breakdown.
        """
        # Calculate individual components
        state_quality = self._calculate_state_quality(current_state, metrics)
        transition_strength = self._calculate_transition_strength(metrics)
        weekly_structure = self._calculate_weekly_structure(metrics)
        rs_stability = self._calculate_rs_stability(metrics)
        regime_alignment = self._calculate_regime_alignment(current_state, market_regime)
        pullback_quality = self._calculate_pullback_quality(metrics)
        
        # Calculate weighted priority score
        priority_score = (
            state_quality * 0.30 +
            transition_strength * 0.25 +
            weekly_structure * 0.15 +
            rs_stability * 0.10 +
            regime_alignment * 0.10 +
            pullback_quality * 0.10
        )
        
        return SetupPriority(
            symbol=metrics.symbol,
            priority_score=priority_score,
            state_quality=state_quality,
            transition_strength=transition_strength,
            weekly_structure=weekly_structure,
            rs_stability=rs_stability,
            regime_alignment=regime_alignment,
            pullback_quality=pullback_quality,
            current_state=current_state
        )
    
    def rank_setups(
        self,
        setups: List[SetupPriority],
        limit: int = 6,
        min_score: float = 50.0
    ) -> List[SetupPriority]:
        """
        Rank setups by priority_score and return top N.
        
        Args:
            setups: List of SetupPriority objects
            limit: Maximum number of setups to return
            min_score: Minimum priority_score threshold (lowered to 50 for more setups)
        
        Returns:
            List of SetupPriority objects ranked by priority_score
        """
        # Filter by minimum score
        valid_setups = [s for s in setups if s.priority_score >= min_score]
        
        # Sort by priority_score descending
        valid_setups.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Return top N
        return valid_setups[:limit]
    
    def _calculate_state_quality(self, state: SetupState, metrics: StockMetrics) -> float:
        """
        Calculate state quality score (0-100) using contextual scoring.
        
        State quality reflects the operational value of the current state,
        but now uses ContextualSetupEngine for sophisticated, volatility-aware
        scoring instead of simple state mapping.
        
        Philosophy:
        - Structure > Distance
        - Volatility-aware positioning
        - Contextual thresholds
        """
        # Use ContextualSetupEngine for sophisticated scoring
        readiness_score = self.contextual_engine.calculate_readiness_score(metrics)
        
        # Adjust score based on state operational priority
        # This is a multiplier that reflects the operational urgency of the state
        state_priority_multiplier = {
            # Pre-reclaim (foco del sistema)
            SetupState.TIGHTENING:             1.20,  # highest pre-reclaim quality
            SetupState.VOLATILITY_CONTRACTION: 1.15,
            SetupState.RECLAIM_PREPARATION:    1.15,
            SetupState.SUPPORT_TESTING:        1.10,
            SetupState.UNDERCUT:               1.10,
            SetupState.CONTROLLED_PULLBACK:    1.05,
            SetupState.EARLY_PULLBACK:         1.00,
            # Continuation/reclaim
            SetupState.CONTINUATION:           1.10,
            SetupState.RECLAIM_IN_PROGRESS:    1.00,
            # Deterioration
            SetupState.DISTRIBUTION:           0.70,
            SetupState.DISTRIBUTION:           0.70,
            SetupState.BROKEN:                 0.40,
        }
        
        multiplier = state_priority_multiplier.get(state, 1.0)
        
        # Apply multiplier to contextual readiness score
        contextual_state_quality = readiness_score.total_score * multiplier
        
        return min(100.0, max(0.0, contextual_state_quality))
    
    def _calculate_transition_strength(self, metrics: StockMetrics) -> float:
        """
        Calculate transition strength score (0-100).
        
        Reflects the momentum and direction of the setup.
        Simplified version using proxy indicators.
        """
        # For now, use pullback quality as proxy for transition strength
        # In full implementation, this would track historical transitions
        if metrics.pullback_quality_score is not None:
            return metrics.pullback_quality_score
        
        return 50.0  # Default neutral
    
    def _calculate_weekly_structure(self, metrics: StockMetrics) -> float:
        """
        Calculate weekly structure score (0-100).
        
        Reflects the quality of the weekly base structure.
        """
        if metrics.weekly_trend_quality is not None:
            return metrics.weekly_trend_quality * 100
        
        return 50.0  # Default neutral
    
    def _calculate_rs_stability(self, metrics: StockMetrics) -> float:
        """
        Calculate RS stability score (0-100).
        
        Reflects the stability and strength of relative strength.
        """
        if metrics.relative_strength_spy is not None:
            rs = metrics.relative_strength_spy
            
            if rs >= 110:
                return 100.0  # Excellent - significantly outperforming
            elif rs >= 105:
                return 80.0   # Good - outperforming
            elif rs >= 100:
                return 60.0   # Fair - matching market
            elif rs >= 95:
                return 40.0   # Poor - underperforming
            else:
                return 20.0   # Very poor - significantly underperforming
        
        return 50.0  # Default neutral
    
    def _calculate_regime_alignment(
        self,
        state: SetupState,
        market_regime: Optional[str]
    ) -> float:
        """
        Calculate regime alignment score (0-100).
        
        Reflects how well the setup aligns with current market regime.
        """
        if market_regime is None:
            return 50.0  # Default neutral if regime unknown
        
        regime = market_regime.lower()
        
        # Define alignment matrix
        # Rows: setup states, Columns: market regimes
        alignment_matrix = {
            SetupState.RECLAIM_PREPARATION: {
                "risk_on": 100.0, "transition": 60.0, "risk_off": 25.0, "choppy": 55.0
            },
            SetupState.CONTINUATION: {
                "risk_on": 100.0, "transition": 55.0, "risk_off": 20.0, "choppy": 50.0
            },
            SetupState.TIGHTENING: {
                "risk_on": 85.0, "transition": 60.0, "risk_off": 35.0, "choppy": 55.0
            },
            SetupState.VOLATILITY_CONTRACTION: {
                "risk_on": 80.0, "transition": 55.0, "risk_off": 30.0, "choppy": 50.0
            },
            SetupState.CONTROLLED_PULLBACK: {
                "risk_on": 75.0, "transition": 50.0, "risk_off": 25.0, "choppy": 50.0
            },
            SetupState.SUPPORT_TESTING: {
                "risk_on": 70.0, "transition": 50.0, "risk_off": 35.0, "choppy": 50.0
            },
            SetupState.UNDERCUT: {
                "risk_on": 65.0, "transition": 45.0, "risk_off": 30.0, "choppy": 45.0
            },
            SetupState.EARLY_PULLBACK: {
                "risk_on": 60.0, "transition": 40.0, "risk_off": 20.0, "choppy": 40.0
            },
            SetupState.RECLAIM_IN_PROGRESS: {
                "risk_on": 65.0, "transition": 40.0, "risk_off": 20.0, "choppy": 40.0
            },
            SetupState.DISTRIBUTION: {
                "risk_on": 20.0, "transition": 20.0, "risk_off": 10.0, "choppy": 20.0
            },
            SetupState.BROKEN: {
                "risk_on": 0.0,  "transition": 0.0,  "risk_off": 0.0,  "choppy": 0.0
            }
        }
        
        state_alignments = alignment_matrix.get(state, {})
        return state_alignments.get(regime, 50.0)
    
    def _calculate_pullback_quality(self, metrics: StockMetrics) -> float:
        """
        Calculate pullback quality score (0-100).
        
        Reflects the quality of the current pullback structure.
        """
        if metrics.pullback_quality_score is not None:
            return metrics.pullback_quality_score
        
        return 50.0  # Default neutral
    
    def get_priority_summary(self, ranked_setups: List[SetupPriority]) -> dict:
        """
        Get summary statistics for ranked setups.
        
        Returns:
            - total_analyzed
            - total_passed_threshold
            - avg_priority_score
            - top_setup
            - state_distribution
        """
        if not ranked_setups:
            return {
                "total_analyzed": 0,
                "total_passed_threshold": 0,
                "avg_priority_score": 0.0,
                "top_setup": None,
                "state_distribution": {}
            }
        
        total_passed = len(ranked_setups)
        avg_score = sum(s.priority_score for s in ranked_setups) / total_passed
        top_setup = ranked_setups[0] if ranked_setups else None
        
        # Calculate state distribution
        state_dist = {}
        for setup in ranked_setups:
            state = setup.current_state.value
            state_dist[state] = state_dist.get(state, 0) + 1
        
        return {
            "total_analyzed": total_passed,
            "total_passed_threshold": total_passed,
            "avg_priority_score": avg_score,
            "top_setup": top_setup.get_breakdown() if top_setup else None,
            "state_distribution": state_dist
        }
