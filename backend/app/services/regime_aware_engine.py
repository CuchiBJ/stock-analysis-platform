"""Regime-Aware Setup Model - Adjust confidence based on market regime"""

from enum import Enum
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.setup_lifecycle_engine import SetupState
from app.services.market_regime_engine import MarketRegime
import logging

logger = logging.getLogger(__name__)


class RegimeImpact(Enum):
    """Impact of market regime on setup confidence"""
    STRONGLY_POSITIVE = "strongly_positive"  # Significantly increases confidence
    POSITIVE = "positive"                    # Moderately increases confidence
    NEUTRAL = "neutral"                      # No significant impact
    NEGATIVE = "negative"                    # Moderately decreases confidence
    STRONGLY_NEGATIVE = "strongly_negative"  # Significantly decreases confidence


@dataclass
class RegimeAdjustment:
    """Adjustment to setup confidence based on market regime"""
    original_confidence: float
    adjusted_confidence: float
    regime: str
    regime_impact: RegimeImpact
    adjustment_factor: float
    rationale: str


class RegimeAwareEngine:
    """
    Regime-Aware Setup Model - Adjust confidence based on market regime.
    
    Core philosophy: Setup confidence should be dynamically adjusted based on
    current market conditions. High-quality setups in adverse market conditions
    should have reduced confidence, while moderate setups in favorable conditions
    can have increased confidence.
    
    Expected outcome:
    - Dynamic confidence adjustment based on market regime
    - Reduced false positives in adverse conditions
    - Improved risk management through regime-aware positioning
    - Better alignment of setup quality with market opportunity
    """
    
    # Regime definitions and their impact on setup types
    REGIME_SETUP_MATRIX = {
        # Risk ON regimes - favorable for continuation and breakout setups
        "strong_bullish": {
            SetupState.CONTINUATION: RegimeImpact.STRONGLY_POSITIVE,
            SetupState.TRIGGER_READY: RegimeImpact.STRONGLY_POSITIVE,
            SetupState.TIGHTENING: RegimeImpact.POSITIVE,
            SetupState.CONSTRUCTIVE_PULLBACK: RegimeImpact.POSITIVE,
            SetupState.EMERGING: RegimeImpact.NEUTRAL,
            SetupState.WEAKENING: RegimeImpact.NEGATIVE,
            SetupState.BROKEN: RegimeImpact.STRONGLY_NEGATIVE
        },
        "bullish": {
            SetupState.CONTINUATION: RegimeImpact.POSITIVE,
            SetupState.TRIGGER_READY: RegimeImpact.POSITIVE,
            SetupState.TIGHTENING: RegimeImpact.POSITIVE,
            SetupState.CONSTRUCTIVE_PULLBACK: RegimeImpact.NEUTRAL,
            SetupState.EMERGING: RegimeImpact.NEUTRAL,
            SetupState.WEAKENING: RegimeImpact.NEGATIVE,
            SetupState.BROKEN: RegimeImpact.NEGATIVE
        },
        # Risk OFF regimes - favorable for pullback and defensive setups
        "strong_bearish": {
            SetupState.CONSTRUCTIVE_PULLBACK: RegimeImpact.POSITIVE,
            SetupState.EMERGING: RegimeImpact.NEUTRAL,
            SetupState.TIGHTENING: RegimeImpact.NEGATIVE,
            SetupState.TRIGGER_READY: RegimeImpact.STRONGLY_NEGATIVE,
            SetupState.CONTINUATION: RegimeImpact.STRONGLY_NEGATIVE,
            SetupState.WEAKENING: RegimeImpact.STRONGLY_NEGATIVE,
            SetupState.BROKEN: RegimeImpact.STRONGLY_NEGATIVE
        },
        "bearish": {
            SetupState.CONSTRUCTIVE_PULLBACK: RegimeImpact.POSITIVE,
            SetupState.EMERGING: RegimeImpact.NEUTRAL,
            SetupState.TIGHTENING: RegimeImpact.NEUTRAL,
            SetupState.TRIGGER_READY: RegimeImpact.NEGATIVE,
            SetupState.CONTINUATION: RegimeImpact.NEGATIVE,
            SetupState.WEAKENING: RegimeImpact.NEGATIVE,
            SetupState.BROKEN: RegimeImpact.NEGATIVE
        },
        # Neutral regimes - baseline confidence
        "choppy": {
            SetupState.CONTINUATION: RegimeImpact.NEUTRAL,
            SetupState.TRIGGER_READY: RegimeImpact.NEUTRAL,
            SetupState.TIGHTENING: RegimeImpact.NEUTRAL,
            SetupState.CONSTRUCTIVE_PULLBACK: RegimeImpact.NEUTRAL,
            SetupState.EMERGING: RegimeImpact.NEUTRAL,
            SetupState.WEAKENING: RegimeImpact.NEUTRAL,
            SetupState.BROKEN: RegimeImpact.NEUTRAL
        }
    }
    
    # Confidence adjustment factors
    ADJUSTMENT_FACTORS = {
        RegimeImpact.STRONGLY_POSITIVE: 1.3,  # +30% confidence
        RegimeImpact.POSITIVE: 1.15,          # +15% confidence
        RegimeImpact.NEUTRAL: 1.0,            # No adjustment
        RegimeImpact.NEGATIVE: 0.85,          # -15% confidence
        RegimeImpact.STRONGLY_NEGATIVE: 0.6  # -40% confidence
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def calculate_regime_adjustment(
        self,
        setup_state: SetupState,
        original_confidence: float,
        market_regime: MarketRegime
    ) -> RegimeAdjustment:
        """
        Calculate confidence adjustment based on market regime.
        
        Args:
            setup_state: Current state of the setup
            original_confidence: Original confidence score (0-1)
            market_regime: Current market regime object
        
        Returns:
            RegimeAdjustment with adjusted confidence and rationale
        """
        # Get regime impact for this setup state
        regime_impact = self._get_regime_impact(setup_state, market_regime.regime)
        
        # Get adjustment factor
        adjustment_factor = self.ADJUSTMENT_FACTORS.get(regime_impact, 1.0)
        
        # Calculate adjusted confidence
        adjusted_confidence = min(1.0, original_confidence * adjustment_factor)
        
        # Generate rationale
        rationale = self._generate_rationale(
            setup_state, 
            market_regime.regime, 
            regime_impact,
            market_regime.breadth_quality,
            market_regime.speculative_appetite
        )
        
        return RegimeAdjustment(
            original_confidence=original_confidence,
            adjusted_confidence=adjusted_confidence,
            regime=market_regime.regime,
            regime_impact=regime_impact,
            adjustment_factor=adjustment_factor,
            rationale=rationale
        )
    
    def get_regime_setup_priority(
        self,
        market_regime: MarketRegime
    ) -> Dict[SetupState, float]:
        """
        Get priority weights for each setup state based on current regime.
        
        Returns dictionary mapping setup states to priority weights (0-1).
        Higher weights indicate setups that are more favorable in current regime.
        """
        regime = market_regime.regime
        setup_matrix = self.REGIME_SETUP_MATRIX.get(regime, self.REGIME_SETUP_MATRIX["choppy"])
        
        priority_weights = {}
        for state, impact in setup_matrix.items():
            # Convert impact to priority weight
            if impact == RegimeImpact.STRONGLY_POSITIVE:
                priority_weights[state] = 1.0
            elif impact == RegimeImpact.POSITIVE:
                priority_weights[state] = 0.8
            elif impact == RegimeImpact.NEUTRAL:
                priority_weights[state] = 0.5
            elif impact == RegimeImpact.NEGATIVE:
                priority_weights[state] = 0.2
            elif impact == RegimeImpact.STRONGLY_NEGATIVE:
                priority_weights[state] = 0.0
        
        return priority_weights
    
    def should_reduce_exposure(
        self,
        market_regime: MarketRegime
    ) -> Tuple[bool, str]:
        """
        Determine if overall exposure should be reduced based on market regime.
        
        Returns tuple of (should_reduce, rationale)
        """
        regime = market_regime.regime
        breadth_quality = market_regime.breadth_quality
        speculative_appetite = market_regime.speculative_appetite
        confidence = market_regime.confidence
        
        # Strong bearish conditions - reduce exposure
        if regime in ["strong_bearish", "bearish"]:
            return True, f"Market regime is {regime}. Reduce exposure to defensive setups only."
        
        # Poor breadth quality - reduce exposure
        if breadth_quality < 0.3:
            return True, f"Breadth quality is poor ({breadth_quality:.2f}). Reduce exposure."
        
        # Low confidence in regime detection - reduce exposure
        if confidence < 0.7:
            return True, f"Low regime detection confidence ({confidence:.2f}). Reduce exposure."
        
        # Speculative appetite too high - risk of blow-off top
        if speculative_appetite > 0.8 and regime in ["bullish", "strong_bullish"]:
            return True, f"Excessive speculative appetite ({speculative_appetite:.2f}). Reduce exposure."
        
        return False, "Market conditions are favorable for normal exposure."
    
    def get_optimal_setup_types(
        self,
        market_regime: MarketRegime
    ) -> Tuple[SetupState, SetupState]:
        """
        Get optimal and suboptimal setup types for current regime.
        
        Returns tuple of (optimal_state, suboptimal_state)
        """
        priority_weights = self.get_regime_setup_priority(market_regime)
        
        # Sort states by priority weight
        sorted_states = sorted(
            priority_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        if not sorted_states:
            return (SetupState.EMERGING, SetupState.BROKEN)
        
        optimal_state = sorted_states[0][0]
        suboptimal_state = sorted_states[-1][0]
        
        return (optimal_state, suboptimal_state)
    
    # --- Helper methods ---
    
    def _get_regime_impact(
        self,
        setup_state: SetupState,
        regime: str
    ) -> RegimeImpact:
        """Get regime impact for a specific setup state"""
        setup_matrix = self.REGIME_SETUP_MATRIX.get(regime, self.REGIME_SETUP_MATRIX["choppy"])
        return setup_matrix.get(setup_state, RegimeImpact.NEUTRAL)
    
    def _generate_rationale(
        self,
        setup_state: SetupState,
        regime: str,
        regime_impact: RegimeImpact,
        breadth_quality: float,
        speculative_appetite: float
    ) -> str:
        """Generate rationale for regime adjustment"""
        impact_descriptions = {
            RegimeImpact.STRONGLY_POSITIVE: "Strongly favorable",
            RegimeImpact.POSITIVE: "Favorable",
            RegimeImpact.NEUTRAL: "Neutral",
            RegimeImpact.NEGATIVE: "Unfavorable",
            RegimeImpact.STRONGLY_NEGATIVE: "Strongly unfavorable"
        }
        
        impact_desc = impact_descriptions.get(regime_impact, "Unknown")
        
        rationale = (
            f"Market regime is {regime} ({impact_desc} for {setup_state.value}). "
            f"Breadth quality: {breadth_quality:.2f}, "
            f"Speculative appetite: {speculative_appetite:.2f}."
        )
        
        return rationale
