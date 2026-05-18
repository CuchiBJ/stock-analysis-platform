"""Transition-Focused Model - Track transition strength and setup evolution"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.stock import StockMetrics
from app.services.setup_lifecycle_engine import SetupState, StateTransition
import logging

logger = logging.getLogger(__name__)


class TransitionStrength(Enum):
    """Strength of state transition"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class TransitionDirection(Enum):
    """Direction of transition (progressive vs regressive)"""
    PROGRESSIVE = "progressive"  # Moving toward continuation (e.g., emerging -> tightening)
    REGRESSIVE = "regressive"    # Moving away from continuation (e.g., continuation -> weakening)
    LATERAL = "lateral"         # Neutral transition


class OperationalTransition(Enum):
    """Operational transition within a state"""
    IMPROVING = "improving"      # Setup is improving (RS up, volume contracting, structure tightening)
    TIGHTENING = "tightening"    # Setup is compacting (range narrowing, volume drying)
    STABLE = "stable"           # Setup is stable (no significant change)
    WEAKENING = "weakening"    # Setup is deteriorating (RS down, volume expanding, structure weakening)
    FAILING = "failing"         # Setup is failing (EMA21 lost, breakdown, distribution)
    RECLAIMING = "reclaiming"  # Setup is reclaiming EMA21
    STABILIZING = "stabilizing"  # Setup is stabilizing after volatility


class FreshnessState(Enum):
    """Freshness of a setup"""
    FRESH = "fresh"           # 0-3 days in current state
    AGING = "aging"           # 4-7 days in current state
    LATE_STAGE = "late_stage" # 8-14 days in current state
    STALE = "stale"           # 15+ days in current state
    EXTENDED = "extended"     # 20+ days in current state


@dataclass
class TransitionMetrics:
    """Metrics for a state transition"""
    from_state: SetupState
    to_state: SetupState
    strength: TransitionStrength
    direction: TransitionDirection
    quality_score: float
    structural_health: float
    transition_duration_hours: float
    price_change_pct: float
    volume_change_pct: float
    confidence: float


@dataclass
class OperationalTransitionMetrics:
    """Metrics for operational transition within a state"""
    transition: OperationalTransition
    strength: float  # 0-1, strength of the transition
    rs_change: float  # RS change points
    volume_change_pct: float  # Volume change percentage
    structure_change: float  # Structure quality change
    narrative: str  # Short operational narrative
    timestamp: datetime


@dataclass
class FreshnessMetrics:
    """Freshness tracking for a setup"""
    state: FreshnessState
    days_in_state: int
    days_since_reclaim: int
    days_since_trigger: int
    setup_decay: float  # 0-1, decay factor
    freshness_score: float  # 0-1, higher is fresher


@dataclass
class SetupEvolution:
    """Evolution tracking for a setup over time"""
    symbol: str
    transitions: List[TransitionMetrics]
    current_state: SetupState
    time_in_current_state_hours: float
    overall_health_score: float
    transition_quality_trend: str  # "improving", "stable", "deteriorating"
    expected_next_state: Optional[SetupState]
    expected_transition_confidence: float


class TransitionEngine:
    """
    Transition-Focused Model - Track transition strength and setup evolution.
    
    Core philosophy: The quality of state transitions is as important as the
    current state itself. Strong, progressive transitions indicate institutional
    accumulation and structural integrity. Weak or regressive transitions signal
    distribution or failed setups.
    
    Expected outcome: 
    - Identify setups with strong progressive transitions (high conviction)
    - Detect early signs of setup deterioration (regressive transitions)
    - Measure setup evolution quality over time (institutional vs retail)
    """
    
    # State progression order (from worst to best)
    STATE_HIERARCHY = {
        SetupState.BROKEN: 0,
        SetupState.WEAKENING: 1,
        SetupState.EMERGING: 2,
        SetupState.CONSTRUCTIVE_PULLBACK: 3,
        SetupState.TIGHTENING: 4,
        SetupState.TRIGGER_READY: 5,
        SetupState.CONTINUATION: 6
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_operational_transition(
        self,
        symbol: str,
        current_metrics: StockMetrics,
        previous_metrics: Optional[StockMetrics] = None
    ) -> OperationalTransitionMetrics:
        """
        Calculate operational transition within current state.
        
        Returns transition type (improving/tightening/stable/weakening/failing)
        based on RS change, volume change, and structure change.
        """
        if not previous_metrics:
            # No previous data, assume stable
            return OperationalTransitionMetrics(
                transition=OperationalTransition.STABLE,
                strength=0.5,
                rs_change=0.0,
                volume_change_pct=0.0,
                structure_change=0.0,
                narrative="No previous data for comparison.",
                timestamp=datetime.utcnow()
            )
        
        # Calculate changes including EMA21 distance change
        ema21_distance_change = 0.0
        if (current_metrics.distance_to_ema21 is not None and 
            previous_metrics.distance_to_ema21 is not None):
            ema21_distance_change = current_metrics.distance_to_ema21 - previous_metrics.distance_to_ema21
        
        rs_change = 0.0
        if current_metrics.relative_strength_spy and previous_metrics.relative_strength_spy:
            rs_change = current_metrics.relative_strength_spy - previous_metrics.relative_strength_spy
        
        volume_change_pct = 0.0
        if (current_metrics.relative_volume and previous_metrics.relative_volume and 
            previous_metrics.relative_volume > 0):
            volume_change_pct = ((current_metrics.relative_volume - previous_metrics.relative_volume) / 
                               previous_metrics.relative_volume) * 100
        
        structure_change = 0.0
        if (current_metrics.weekly_tightness and previous_metrics.weekly_tightness):
            structure_change = current_metrics.weekly_tightness - previous_metrics.weekly_tightness
        
        # Determine transition type
        transition = self._determine_operational_transition(
            rs_change, volume_change_pct, structure_change, ema21_distance_change, current_metrics
        )
        
        # Calculate strength
        strength = self._calculate_operational_transition_strength(
            rs_change, volume_change_pct, structure_change, transition
        )
        
        # Generate narrative
        narrative = self._generate_operational_narrative(
            transition, rs_change, volume_change_pct, structure_change, current_metrics
        )
        
        return OperationalTransitionMetrics(
            transition=transition,
            strength=strength,
            rs_change=rs_change,
            volume_change_pct=volume_change_pct,
            structure_change=structure_change,
            narrative=narrative,
            timestamp=datetime.utcnow()
        )
    
    async def calculate_freshness(
        self,
        symbol: str,
        current_state: SetupState,
        days_in_state: int,
        days_since_reclaim: Optional[int] = None,
        days_since_trigger: Optional[int] = None
    ) -> FreshnessMetrics:
        """
        Calculate freshness metrics for a setup.
        
        Freshness state based on days in current state.
        Setup decay increases with time in state.
        """
        # Determine freshness state
        if days_in_state <= 3:
            freshness_state = FreshnessState.FRESH
            freshness_score = 1.0
        elif days_in_state <= 7:
            freshness_state = FreshnessState.AGING
            freshness_score = 0.7
        elif days_in_state <= 14:
            freshness_state = FreshnessState.LATE_STAGE
            freshness_score = 0.4
        elif days_in_state <= 19:
            freshness_state = FreshnessState.STALE
            freshness_score = 0.2
        else:
            freshness_state = FreshnessState.EXTENDED
            freshness_score = 0.1
        
        # Calculate setup decay (0-1, higher = more decayed)
        # Decay increases exponentially with days in state
        setup_decay = min(1.0, days_in_state / 30.0)
        
        # Adjust decay if recent reclaim (fresher)
        if days_since_reclaim and days_since_reclaim <= 3:
            setup_decay *= 0.5
            freshness_score = min(1.0, freshness_score + 0.2)
        
        return FreshnessMetrics(
            state=freshness_state,
            days_in_state=days_in_state,
            days_since_reclaim=days_since_reclaim or 0,
            days_since_trigger=days_since_trigger or 0,
            setup_decay=setup_decay,
            freshness_score=freshness_score
        )
    
    def calculate_transition_strength(
        self,
        from_state: SetupState,
        to_state: SetupState,
        old_metrics: StockMetrics,
        new_metrics: StockMetrics
    ) -> TransitionStrength:
        """
        Calculate the strength of a state transition.
        
        Based on:
        - Quality of price action during transition
        - Volume pattern (supportive vs distributive)
        - Speed of transition (gradual vs abrupt)
        - Structural integrity maintained
        """
        strength_score = 0.0
        
        # 1. Price action quality (40%)
        price_change = self._calculate_price_change(old_metrics, new_metrics)
        if price_change > 0:  # Price increased during transition
            strength_score += min(0.4, price_change / 10.0)  # Normalize
        elif price_change < -2:  # Significant decline
            strength_score -= 0.2
        
        # 2. Volume pattern (30%)
        volume_quality = self._calculate_volume_quality(old_metrics, new_metrics)
        strength_score += volume_quality * 0.3
        
        # 3. Structural integrity (20%)
        structural_score = self._calculate_structural_integrity(old_metrics, new_metrics)
        strength_score += structural_score * 0.2
        
        # 4. Direction quality (10%)
        direction = self._determine_transition_direction(from_state, to_state)
        if direction == TransitionDirection.PROGRESSIVE:
            strength_score += 0.1
        elif direction == TransitionDirection.REGRESSIVE:
            strength_score -= 0.1
        
        # Classify strength
        if strength_score >= 0.8:
            return TransitionStrength.VERY_STRONG
        elif strength_score >= 0.6:
            return TransitionStrength.STRONG
        elif strength_score >= 0.3:
            return TransitionStrength.MODERATE
        else:
            return TransitionStrength.WEAK
    
    def determine_transition_direction(
        self,
        from_state: SetupState,
        to_state: SetupState
    ) -> TransitionDirection:
        """
        Determine if transition is progressive (toward continuation) or regressive.
        
        Progressive: Moving up the state hierarchy (e.g., emerging -> tightening)
        Regressive: Moving down the state hierarchy (e.g., continuation -> weakening)
        Lateral: Neutral transition
        """
        from_level = self.STATE_HIERARCHY.get(from_state, 0)
        to_level = self.STATE_HIERARCHY.get(to_state, 0)
        
        if to_level > from_level:
            return TransitionDirection.PROGRESSIVE
        elif to_level < from_level:
            return TransitionDirection.REGRESSIVE
        else:
            return TransitionDirection.LATERAL
    
    def track_setup_evolution(
        self,
        symbol: str,
        transitions: List[TransitionMetrics]
    ) -> SetupEvolution:
        """
        Track the complete evolution of a setup over time.
        
        Analyzes:
        - Transition quality trend (improving, stable, deteriorating)
        - Time spent in each state
        - Overall setup health
        - Expected next state based on pattern
        """
        if not transitions:
            return None
        
        current_state = transitions[-1].to_state
        
        # Calculate time in current state
        time_in_current_state = transitions[-1].transition_duration_hours
        
        # Calculate overall health score
        overall_health = self._calculate_oversetup_health(transitions)
        
        # Determine transition quality trend
        trend = self._determine_transition_trend(transitions)
        
        # Predict next state
        expected_next_state, confidence = self._predict_next_state(
            current_state, transitions
        )
        
        return SetupEvolution(
            symbol=symbol,
            transitions=transitions,
            current_state=current_state,
            time_in_current_state_hours=time_in_current_state,
            overall_health_score=overall_health,
            transition_quality_trend=trend,
            expected_next_state=expected_next_state,
            expected_transition_confidence=confidence
        )
    
    def get_transition_statistics(
        self,
        symbol: str,
        days_back: int = 30
    ) -> Dict:
        """
        Get transition statistics for a symbol over a time period.
        
        Returns:
        - Total transitions
        - Progressive vs regressive ratio
        - Average transition strength
        - Most common transitions
        - State duration averages
        """
        # This would require historical data tracking
        # For now, return placeholder
        return {
            "total_transitions": 0,
            "progressive_count": 0,
            "regressive_count": 0,
            "progressive_ratio": 0.0,
            "average_strength": 0.0,
            "most_common_transitions": [],
            "average_state_duration_hours": 0.0
        }
    
    # --- Helper methods ---
    
    def _calculate_price_change(
        self,
        old_metrics: StockMetrics,
        new_metrics: StockMetrics
    ) -> float:
        """Calculate percentage price change during transition"""
        if not old_metrics.current_price or not new_metrics.current_price:
            return 0.0
        return ((new_metrics.current_price - old_metrics.current_price) / 
                old_metrics.current_price) * 100
    
    def _calculate_volume_quality(
        self,
        old_metrics: StockMetrics,
        new_metrics: StockMetrics
    ) -> float:
        """
        Calculate volume quality score (0-1).
        
        High quality: Volume contracting during tightening, supportive during pullbacks
        Low quality: Excessive volume during distribution, declining during continuation
        """
        if not old_metrics.avg_volume_10d or not new_metrics.avg_volume_10d:
            return 0.5  # Neutral if no data
        
        volume_change = ((new_metrics.avg_volume_10d - old_metrics.avg_volume_10d) /
                        old_metrics.avg_volume_10d)
        
        # Supportive volume (moderate increase or contraction)
        if -0.3 <= volume_change <= 0.5:
            return 1.0
        # Excessive volume (potential distribution)
        elif volume_change > 1.0:
            return 0.2
        # Drying up volume (potential lack of interest)
        elif volume_change < -0.5:
            return 0.3
        else:
            return 0.6  # Moderate
    
    def _calculate_structural_integrity(
        self,
        old_metrics: StockMetrics,
        new_metrics: StockMetrics
    ) -> float:
        """
        Calculate structural integrity score (0-1).
        
        Based on:
        - EMA21 distance maintenance
        - Weekly structure quality
        - Pullback quality preservation
        """
        integrity_score = 0.5  # Base score
        
        # EMA21 integrity
        if (old_metrics.distance_to_ema21 is not None and 
            new_metrics.distance_to_ema21 is not None):
            # If maintaining EMA21, higher integrity
            if abs(new_metrics.distance_to_ema21) <= 5:
                integrity_score += 0.2
            # If losing EMA21 significantly, lower integrity
            elif new_metrics.distance_to_ema21 < -10:
                integrity_score -= 0.3
        
        # Weekly structure integrity
        if (old_metrics.weekly_trend_quality and 
            new_metrics.weekly_trend_quality):
            if new_metrics.weekly_trend_quality >= old_metrics.weekly_trend_quality:
                integrity_score += 0.2
            else:
                integrity_score -= 0.1
        
        # Pullback quality integrity
        if (old_metrics.pullback_quality_score and 
            new_metrics.pullback_quality_score):
            if new_metrics.pullback_quality_score >= old_metrics.pullback_quality_score:
                integrity_score += 0.1
        
        return max(0.0, min(1.0, integrity_score))
    
    def _determine_transition_direction(
        self,
        from_state: SetupState,
        to_state: SetupState
    ) -> TransitionDirection:
        """Determine transition direction"""
        from_level = self.STATE_HIERARCHY.get(from_state, 0)
        to_level = self.STATE_HIERARCHY.get(to_state, 0)
        
        if to_level > from_level:
            return TransitionDirection.PROGRESSIVE
        elif to_level < from_level:
            return TransitionDirection.REGRESSIVE
        else:
            return TransitionDirection.LATERAL
    
    def _calculate_oversetup_health(
        self,
        transitions: List[TransitionMetrics]
    ) -> float:
        """Calculate overall setup health based on transition history"""
        if not transitions:
            return 0.5
        
        # Weight recent transitions more heavily
        weights = [0.1, 0.2, 0.3, 0.4]  # Oldest to newest
        
        health_sum = 0.0
        total_weight = 0.0
        
        for i, transition in enumerate(reversed(transitions[-4:])):
            weight = weights[min(i, len(weights) - 1)]
            
            # Base score from structural health
            score = transition.structural_health
            
            # Adjust for transition direction
            if transition.direction == TransitionDirection.PROGRESSIVE:
                score += 0.1
            elif transition.direction == TransitionDirection.REGRESSIVE:
                score -= 0.1
            
            # Adjust for transition strength
            if transition.strength == TransitionStrength.VERY_STRONG:
                score += 0.1
            elif transition.strength == TransitionStrength.WEAK:
                score -= 0.1
            
            health_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.5
        
        return max(0.0, min(1.0, health_sum / total_weight))
    
    def _determine_transition_trend(
        self,
        transitions: List[TransitionMetrics]
    ) -> str:
        """Determine if transition quality is improving, stable, or deteriorating"""
        if len(transitions) < 2:
            return "stable"
        
        # Compare recent transitions to older ones
        recent_avg = sum(t.structural_health for t in transitions[-3:]) / min(3, len(transitions))
        older_avg = sum(t.structural_health for t in transitions[:-3]) / max(1, len(transitions) - 3)
        
        if recent_avg > older_avg + 0.1:
            return "improving"
        elif recent_avg < older_avg - 0.1:
            return "deteriorating"
        else:
            return "stable"
    
    def _predict_next_state(
        self,
        current_state: SetupState,
        transitions: List[TransitionMetrics]
    ) -> Tuple[Optional[SetupState], float]:
        """
        Predict the next state based on transition patterns.
        
        Returns tuple of (predicted_state, confidence)
        """
        current_level = self.STATE_HIERARCHY.get(current_state, 0)
        
        # Simple heuristic: if trend is improving, predict progressive transition
        trend = self._determine_transition_trend(transitions)
        
        if trend == "improving":
            # Predict next higher state
            for state, level in self.STATE_HIERARCHY.items():
                if level == current_level + 1:
                    return (state, 0.6)
        elif trend == "deteriorating":
            # Predict next lower state
            for state, level in self.STATE_HIERARCHY.items():
                if level == current_level - 1:
                    return (state, 0.6)
        
        # Default: no confident prediction
        return (None, 0.0)
    
    # --- Operational transition helper methods ---
    
    def _determine_operational_transition(
        self,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        ema21_distance_change: float,
        current_metrics: StockMetrics
    ) -> OperationalTransition:
        """
        Determine operational transition type based on metrics changes.
        """
        # Check for failing conditions first (highest priority)
        # Failing if below EMA21 and moving further away
        if (current_metrics.distance_to_ema21 is not None and 
            current_metrics.distance_to_ema21 < -5 and 
            ema21_distance_change < -2):
            return OperationalTransition.FAILING
        if (current_metrics.distance_to_ema50 is not None and 
            current_metrics.distance_to_ema50 < -10):
            return OperationalTransition.FAILING
        
        # Check for reclaiming (moving toward EMA21 from below with significant change)
        if (current_metrics.distance_to_ema21 is not None and 
            current_metrics.distance_to_ema21 >= -5 and 
            current_metrics.distance_to_ema21 <= 2 and
            ema21_distance_change > 1.0):
            return OperationalTransition.RECLAIMING
        
        # Check for improving (RS up + volume contracting + structure tightening)
        if rs_change > 2 and volume_change_pct < -20 and structure_change > 0.1:
            return OperationalTransition.IMPROVING
        
        # Check for tightening (volume contracting + structure improving)
        if volume_change_pct < -30 and structure_change > 0.05:
            return OperationalTransition.TIGHTENING
        
        # Check for weakening (RS down + volume expanding + structure deteriorating)
        if rs_change < -2 and volume_change_pct > 20 and structure_change < -0.1:
            return OperationalTransition.WEAKENING
        
        # Check for stabilizing (low volatility, moderate changes)
        if abs(rs_change) < 1 and abs(volume_change_pct) < 15 and abs(structure_change) < 0.05:
            return OperationalTransition.STABILIZING
        
        # Default to stable
        return OperationalTransition.STABLE
    
    def _calculate_operational_transition_strength(
        self,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        transition: OperationalTransition
    ) -> float:
        """
        Calculate strength of operational transition (0-1).
        """
        strength = 0.5  # Base strength
        
        # Adjust based on transition type and magnitude of changes
        if transition == OperationalTransition.IMPROVING:
            # Stronger if RS up significantly and volume contracting strongly
            strength = min(1.0, 0.5 + (rs_change / 10.0) + (abs(volume_change_pct) / 100.0))
        elif transition == OperationalTransition.TIGHTENING:
            # Stronger if volume contracting strongly
            strength = min(1.0, 0.5 + (abs(volume_change_pct) / 80.0))
        elif transition == OperationalTransition.WEAKENING:
            # Stronger if RS down significantly and volume expanding
            strength = min(1.0, 0.5 + (abs(rs_change) / 10.0) + (volume_change_pct / 100.0))
        elif transition == OperationalTransition.FAILING:
            # Stronger if EMA21/EMA50 significantly lost
            strength = 0.9  # Failing is inherently strong
        elif transition == OperationalTransition.RECLAIMING:
            # Stronger if reclaim is recent and clean
            strength = 0.8
        
        return max(0.0, min(1.0, strength))
    
    def _generate_operational_narrative(
        self,
        transition: OperationalTransition,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        current_metrics: StockMetrics
    ) -> str:
        """
        Generate short operational narrative (10-15 words).
        """
        components = []
        
        # Add transition action
        if transition == OperationalTransition.IMPROVING:
            components.append("Setup improving")
        elif transition == OperationalTransition.TIGHTENING:
            components.append("Tightening constructively")
        elif transition == OperationalTransition.WEAKENING:
            components.append("Setup weakening")
        elif transition == OperationalTransition.FAILING:
            components.append("Setup failing")
        elif transition == OperationalTransition.RECLAIMING:
            components.append("Reclaiming EMA21")
        elif transition == OperationalTransition.STABILIZING:
            components.append("Stabilizing")
        else:
            components.append("Stable")
        
        # Add RS detail
        if abs(rs_change) > 2:
            if rs_change > 0:
                components.append(f"RS +{rs_change:.0f}")
            else:
                components.append(f"RS {rs_change:.0f}")
        
        # Add volume detail
        if abs(volume_change_pct) > 20:
            if volume_change_pct < 0:
                components.append(f"Vol {volume_change_pct:.0f}%")
            else:
                components.append(f"Vol +{volume_change_pct:.0f}%")
        
        # Add structure detail
        if abs(structure_change) > 0.1:
            if structure_change > 0:
                components.append("structure tightening")
            else:
                components.append("structure weakening")
        
        # Combine into short narrative
        if len(components) <= 3:
            return ". ".join(components) + "."
        else:
            return ". ".join(components[:3]) + "."
