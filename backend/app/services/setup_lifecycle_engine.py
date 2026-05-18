"""Setup Lifecycle Engine - Model the complete lifecycle of institutional setups"""

from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.stock import Stock, StockMetrics
import logging

logger = logging.getLogger(__name__)


class SetupState(Enum):
    """
    States in the lifecycle of a setup (simplified to 7 states).
    
    Simplified from 11 to 7 states to reduce complexity and improve operational clarity.
    Eliminated intermediate states that don't provide differential operational value.
    """
    EMERGING = "emerging"
    TIGHTENING = "tightening"
    CONSTRUCTIVE_PULLBACK = "constructive_pullback"
    TRIGGER_READY = "trigger_ready"
    CONTINUATION = "continuation"
    WEAKENING = "weakening"
    BROKEN = "broken"


@dataclass
class StateTransition:
    """Record of a state transition"""
    from_state: SetupState
    to_state: SetupState
    timestamp: datetime
    quality_score: float
    structural_health: float


@dataclass
class SetupLifecycle:
    """Complete lifecycle of a setup"""
    symbol: str
    current_state: SetupState
    state_history: List[StateTransition]
    weekly_structure_score: float
    pullback_quality_score: float
    continuation_probability: float
    market_regime_at_entry: str
    leader_health_at_entry: float
    narrative: str


class SetupLifecycleEngine:
    """
    Engine to detect and track the lifecycle of institutional setups.
    
    Core philosophy: Model the complete lifecycle from emergence through
    continuation or failure, focusing on structural quality and institutional
    trading patterns.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def detect_current_state(self, metrics: StockMetrics) -> SetupState:
        """
        Detect current state based on technical structure (simplified to 7 states).
        
        Rule-based detection (no ML) for interpretability and rapid iteration.
        Simplified logic to reduce false positives and improve selectivity.
        """
        # Check for breakdown/failure states first
        if self._is_broken(metrics):
            return SetupState.BROKEN
        
        if self._is_weakening(metrics):
            return SetupState.WEAKENING
        
        # Check for continuation states
        if self._is_continuation(metrics):
            return SetupState.CONTINUATION
        
        # Check for trigger/entry state (conservative)
        if self._is_trigger_ready(metrics):
            return SetupState.TRIGGER_READY
        
        # Check for pullback state
        if self._is_constructive_pullback(metrics):
            return SetupState.CONSTRUCTIVE_PULLBACK
        
        # Check for early states
        if self._is_tightening(metrics):
            return SetupState.TIGHTENING
        
        if self._is_emerging(metrics):
            return SetupState.EMERGING
        
        # Default to emerging if no clear state
        return SetupState.EMERGING
    
    def detect_state_transition(
        self, 
        symbol: str, 
        old_state: SetupState, 
        new_state: SetupState
    ) -> Optional[StateTransition]:
        """Detect and record state transition"""
        if old_state == new_state:
            return None
        
        # Calculate quality and health at transition
        # This will be implemented when we have historical tracking
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(),
            quality_score=0.0,  # To be calculated
            structural_health=0.0  # To be calculated
        )
        
        logger.info(f"State transition for {symbol}: {old_state.value} -> {new_state.value}")
        return transition
    
    def calculate_continuation_probability(self, metrics: StockMetrics) -> float:
        """
        Calculate continuation probability (rule-based, no ML).
        
        Based on:
        - Weekly structure quality
        - Pullback quality
        - Relative strength
        - Volume pattern
        - Market regime (to be integrated)
        """
        probability = 0.0
        
        # Weekly structure contribution (40%)
        if metrics.weekly_trend_quality:
            probability += metrics.weekly_trend_quality * 0.4
        
        # Pullback quality contribution (30%)
        if metrics.pullback_quality_score:
            # Normalize score to 0-1 range
            normalized_score = min(1.0, metrics.pullback_quality_score / 100.0)
            probability += normalized_score * 0.3
        
        # Relative strength contribution (20%)
        if metrics.relative_strength_spy and metrics.relative_strength_spy > 100:
            rs_strength = (metrics.relative_strength_spy - 100) / 50.0  # Normalize
            probability += min(0.2, rs_strength * 0.2)
        
        # Volume pattern contribution (10%)
        if metrics.volume_contraction and metrics.volume_contraction > 0:
            probability += min(0.1, metrics.volume_contraction * 0.1)
        
        return min(1.0, max(0.0, probability))
    
    def generate_narrative(self, metrics: StockMetrics, state: SetupState) -> str:
        """
        Generate contextual narrative explaining the setup (short operational format).
        
        This provides the "why" behind the setup, not just the "what".
        Simplified to short operational narratives (10-20 words).
        """
        # Pre-calculate values to avoid complex f-string expressions
        weekly_quality = metrics.weekly_trend_quality if metrics.weekly_trend_quality else 0
        weeks_base = metrics.weeks_in_base if metrics.weeks_in_base else 0
        pullback_score = metrics.pullback_quality_score if metrics.pullback_quality_score else 0
        ema21_dist = metrics.distance_to_ema21 if metrics.distance_to_ema21 else 0
        rs_spy = metrics.relative_strength_spy if metrics.relative_strength_spy else 0
        cont_prob = self.calculate_continuation_probability(metrics)
        
        narratives = {
            SetupState.EMERGING: f"Early setup. {weeks_base}-week base. Weekly quality: {weekly_quality:.2f}",
            SetupState.TIGHTENING: f"Tightening. {weeks_base}-week base. Volume contracting.",
            SetupState.CONSTRUCTIVE_PULLBACK: f"Pullback. Score: {pullback_score:.0f}. EMA21: {ema21_dist:.1f}%.",
            SetupState.TRIGGER_READY: f"Trigger ready. Score: {pullback_score:.0f}. Cont prob: {cont_prob:.0%}.",
            SetupState.CONTINUATION: f"Continuation. Holding EMA21. RS: {rs_spy:.0f}.",
            SetupState.WEAKENING: f"Weakening. Lost EMA21. Distribution risk.",
            SetupState.BROKEN: f"Broken. Structure failed. No longer valid."
        }
        
        return narratives.get(state, "State not recognized")
    
    # --- Helper methods for state detection (simplified for 7 states) ---
    
    def _is_broken(self, metrics: StockMetrics) -> bool:
        """Setup is broken - structure failed (conservative threshold)"""
        if metrics.distance_to_ema50 is None:
            return False
        return metrics.distance_to_ema50 < -12  # More than 12% below EMA50 (raised from -10%)
    
    def _is_weakening(self, metrics: StockMetrics) -> bool:
        """Setup is weakening - early signs of failure (conservative threshold)"""
        if metrics.distance_to_ema21 is None:
            return False
        return metrics.distance_to_ema21 < -5  # More than 5% below EMA21 (raised from -3%)
    
    def _is_continuation(self, metrics: StockMetrics) -> bool:
        """Trend continuation confirmed (conservative threshold)"""
        if metrics.distance_to_ema21 is None:
            return False
        return (metrics.distance_to_ema21 >= 0 and 
                metrics.distance_to_ema21 <= 5 and
                metrics.weekly_trend_quality and 
                metrics.weekly_trend_quality > 0.7)  # Raised from 0.6
    
    def _is_trigger_ready(self, metrics: StockMetrics) -> bool:
        """Setup ready for trigger - all criteria met (conservative threshold)"""
        if not metrics.pullback_quality_score:
            return False
        return (metrics.pullback_quality_score >= 75 and  # Raised from 60
                metrics.distance_to_ema21 is not None and
                metrics.distance_to_ema21 >= 0 and
                metrics.distance_to_ema21 <= 2)  # Tighter range (raised from 3%)
    
    def _is_constructive_pullback(self, metrics: StockMetrics) -> bool:
        """Orderly constructive pullback (conservative threshold)"""
        if not metrics.pullback_quality_score:
            return False
        return (metrics.pullback_quality_score >= 60 and  # Raised from 50
                metrics.distance_to_ema21 is not None and
                metrics.distance_to_ema21 < -5 and
                metrics.distance_to_ema21 >= -15)  # Deeper pullback allowed
    
    def _is_tightening(self, metrics: StockMetrics) -> bool:
        """Tightening after initial move (conservative threshold)"""
        if metrics.weekly_tightness is None:
            return False
        return metrics.weekly_tightness > 0.6  # Raised from 0.5
    
    def _is_emerging(self, metrics: StockMetrics) -> bool:
        """Early stage setup"""
        if metrics.weeks_in_base is None:
            return False
        return metrics.weeks_in_base < 3
