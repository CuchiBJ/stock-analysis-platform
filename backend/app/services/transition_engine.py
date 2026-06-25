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
    """
    Operational transition within a state.

    Pre-reclaim signals (primary focus — highest priority in feed):
      ENTERING_PULLBACK, VOLUME_DRY_UP, COMPRESSING,
      FLUSH_AND_RECOVER, SUPPORT_HOLDING

    Reclaim/continuation (exist, not the focus):
      RECLAIMING, CONTINUATION_HOLDING

    Deterioration:
      WEAKENING, DISTRIBUTION, FAILING

    Neutral:
      STABLE, STABILIZING
    """
    # Pre-reclaim (foco — aparecen primero en el feed)
    ENTERING_PULLBACK   = "entering_pullback"   # Primera pérdida EMA9/21, estructura intacta
    VOLUME_DRY_UP       = "volume_dry_up"       # Volume contrayendo debajo de EMAs — señal clave
    COMPRESSING         = "compressing"          # ATR contrayendo debajo de EMAs
    FLUSH_AND_RECOVER   = "flush_and_recover"   # Spike bajo + recovery — undercut constructivo
    SUPPORT_HOLDING     = "support_holding"      # Bounces en zona soporte, institucional defendiendo

    # Pre-breakout (coiling cerca de máximos con volumen seco — punto de compra Minervini)
    BREAKOUT            = "breakout"             # Líder comprimido en máximos, volumen contrayendo

    # Reclaim / continuation (existen, no dominan)
    RECLAIMING          = "reclaiming"           # Recuperando EMA21 — señal tardía
    CONTINUATION_HOLDING = "continuation_holding" # Holding EMA21 con estructura

    # Deterioration
    WEAKENING           = "weakening"            # RS baja, estructura se deteriora
    DISTRIBUTION        = "distribution"         # Volume expansion en baja, RS colapsa
    FAILING             = "failing"              # EMA50 perdida con volumen

    # Neutral
    STABLE              = "stable"
    STABILIZING         = "stabilizing"


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
        SetupState.BROKEN:                 0,
        SetupState.DISTRIBUTION:           1,
        SetupState.EARLY_PULLBACK:         2,
        SetupState.CONTROLLED_PULLBACK:    3,
        SetupState.VOLATILITY_CONTRACTION: 4,
        SetupState.SUPPORT_TESTING:        4,
        SetupState.UNDERCUT:               4,
        SetupState.TIGHTENING:             5,
        SetupState.RECLAIM_PREPARATION:    6,
        SetupState.RECLAIM_IN_PROGRESS:    7,
        SetupState.CONTINUATION:           8,
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
        
        # Calculate changes including EMA distance changes (ATR-normalized)
        ema21_distance_change = 0.0
        if (current_metrics.distance_to_ema21_atr is not None and
            previous_metrics.distance_to_ema21_atr is not None):
            ema21_distance_change = current_metrics.distance_to_ema21_atr - previous_metrics.distance_to_ema21_atr

        ema9_distance_change = 0.0
        if (current_metrics.distance_to_ema9_atr is not None and
            previous_metrics.distance_to_ema9_atr is not None):
            ema9_distance_change = current_metrics.distance_to_ema9_atr - previous_metrics.distance_to_ema9_atr

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
        prev_ema21_atr = previous_metrics.distance_to_ema21_atr
        transition = self._determine_operational_transition(
            rs_change, volume_change_pct, structure_change, ema21_distance_change,
            current_metrics, prev_ema21_atr, ema9_distance_change
        )
        
        # Calculate strength
        strength = self._calculate_operational_transition_strength(
            rs_change, volume_change_pct, structure_change, transition
        )
        
        # Generate narrative
        narrative = self._generate_operational_narrative(
            transition, rs_change, volume_change_pct, structure_change, current_metrics
        )

        # Persist observation for every non-STABLE detection (idempotent)
        if transition != OperationalTransition.STABLE:
            from app.services.outcome_tracker import OutcomeTracker, get_current_regime
            from datetime import date as date_cls
            try:
                today = date_cls.today()
                regime = await get_current_regime(self.db, today)
                tracker = OutcomeTracker(self.db)
                await tracker.record_observation(
                    symbol=symbol,
                    transition_value=transition.value,
                    current_metrics=current_metrics,
                    regime=regime,
                    date_detected=today,
                )
            except Exception as e:
                logger.warning(f"Failed to record observation for {symbol}: {e}")

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
    
    def _is_quality_leader(self, m: StockMetrics) -> bool:
        """Delegates to shared `quality_leader_gate.is_quality_leader`.

        Kept as instance method for call-site compatibility within the engine.
        """
        from app.services.quality_leader_gate import is_quality_leader
        return is_quality_leader(m)

    def _determine_operational_transition(
        self,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        ema21_distance_change: float,
        current_metrics: StockMetrics,
        prev_ema21_atr: Optional[float] = None,
        ema9_distance_change: float = 0.0,
    ) -> OperationalTransition:
        """
        Determine operational transition. PRE-RECLAIM signals have priority.
        Reclaiming is detected last — it is the consequence, not the setup.
        """
        ema21 = current_metrics.distance_to_ema21_atr or 0.0
        ema9  = current_metrics.distance_to_ema9_atr or 0.0
        ema50 = current_metrics.distance_to_ema50_atr or 0.0
        rvol  = current_metrics.relative_volume or 1.0
        rs    = current_metrics.relative_strength_spy or 100.0

        # 1. Failing — highest priority, always detect first
        if ema50 < -2.5 or (ema21 < -2.0 and ema21_distance_change < -0.5):
            return OperationalTransition.FAILING

        # 2. Distribution — volume expansion + RS collapse while below EMA21
        if (ema21 < -0.8 and volume_change_pct > 25 and
                rs < 95 and rs_change < -3):
            return OperationalTransition.DISTRIBUTION

        # 3. Weakening — moderate deterioration
        if rs_change < -2 and volume_change_pct > 15 and structure_change < -0.1:
            return OperationalTransition.WEAKENING

        # 4. Flush and recover — quality leader: volume spike + bounce from below EMA21
        if (self._is_quality_leader(current_metrics) and
                rvol > 1.5 and ema21_distance_change > 0.3 and
                -2.5 <= ema21 <= -0.5):
            return OperationalTransition.FLUSH_AND_RECOVER

        # 5. Volume dry-up — quality leader: volume drying below EMA21, RS holding.
        # Bounded to -2 ATR — deeper means structural break, not operable pullback.
        if (self._is_quality_leader(current_metrics) and
                volume_change_pct < -25 and
                -2.0 <= ema21 < -0.3 and
                rs_change >= -1):
            return OperationalTransition.VOLUME_DRY_UP

        # 6. Compressing — quality leader: structure tightening below EMA21.
        # Bounded to -2 ATR same as volume_dry_up.
        if (self._is_quality_leader(current_metrics) and
                structure_change > 0.08 and
                -2.0 <= ema21 < -0.3 and
                volume_change_pct < 0):
            return OperationalTransition.COMPRESSING

        # 7. Entering pullback — quality leader approaching EMA9 or EMA21 from above.
        # Requires: all 7 Minervini SEPA quality gates AND proximity with decreasing distance.
        # EMA9 has priority over EMA21 when both conditions are met.
        if self._is_quality_leader(current_metrics):
            approaching_ema9 = (0 < ema9 <= 0.5 and ema9_distance_change < 0)
            approaching_ema21 = (0 < ema21 <= 1.0 and ema21_distance_change < 0)
            if approaching_ema9 or approaching_ema21:
                return OperationalTransition.ENTERING_PULLBACK

        # 8. Support holding — quality leader below EMA21, bouncing at EMA50 zone.
        if (self._is_quality_leader(current_metrics) and
                ema21 < 0 and
                -0.5 <= ema50 <= 0.2 and
                ema21_distance_change > 0.1):
            return OperationalTransition.SUPPORT_HOLDING

        # 9. Reclaiming — detected last, it is not the focus.
        # Requires: was below EMA21 last period (prev_ema21_atr < 0)
        #           and now is near/above (ema21 >= -1.0 and moving up).
        if (-1.0 <= ema21 <= 0.2 and ema21_distance_change > 0.2 and
                (prev_ema21_atr is None or prev_ema21_atr < 0)):
            return OperationalTransition.RECLAIMING

        # 10. Breakout (coiling) — quality leader comprimido cerca de máximos con
        # volumen seco. Anticipatorio: NO requiere quiebre confirmado ni expansión
        # de volumen. Versión más específica de STABILIZING (cerca del pivote 52w),
        # por eso se evalúa primero.
        # Umbrales calibrados a la distribución empírica de weekly_tightness en
        # este universo (techo práctico ~0.48, p75 ~0.37); 0.37 = cuartil superior.
        # ema21 acotado por arriba: una base que coilea está PEGADA a su EMA21
        # (la media la alcanza); muy por encima = extendido, no es coiling.
        # La compresión de volumen se mide con volume_contraction (3d vs 20d),
        # NO con el cambio día-a-día (ruidoso tras un spike de volumen).
        high52 = current_metrics.distance_to_high_52w_atr
        tightness = current_metrics.weekly_tightness or 0
        weeks_in_base = current_metrics.weeks_in_base or 0
        vol_contraction = current_metrics.volume_contraction
        if (self._is_quality_leader(current_metrics) and
                0 < ema21 <= 1.5 and                         # cerca de EMA21, no extendido
                high52 is not None and high52 >= -1.0 and    # en/cerca del pivote 52w
                tightness >= 0.37 and                        # base apretada (cuartil sup.)
                weeks_in_base >= 4 and                        # base de duración real
                vol_contraction is not None and vol_contraction > 0 and  # dry-up estructural
                rvol < 0.9):                                  # hoy sin expansión de volumen
            return OperationalTransition.BREAKOUT

        # 11. Stabilizing — quality leader with structure tightening and volume
        # contracting above EMA21. Pre-breakout uptrend complement of COMPRESSING.
        if (self._is_quality_leader(current_metrics) and
                0 <= ema21 <= 2.0 and
                tightness >= 0.3 and
                volume_change_pct < 0):
            return OperationalTransition.STABILIZING

        # 12. Continuation holding — quality leader holding above EMA9 and EMA21,
        # stable or rising distance (not approaching EMA21).
        if (self._is_quality_leader(current_metrics) and
                ema9 >= 0 and
                0 <= ema21 <= 1.5 and
                ema21_distance_change >= 0):
            return OperationalTransition.CONTINUATION_HOLDING

        return OperationalTransition.STABLE
    
    def _calculate_operational_transition_strength(
        self,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        transition: OperationalTransition
    ) -> float:
        """
        Strength (0-1) per transition type.
        Pre-reclaim signals have higher base strength than RECLAIMING.
        """
        base = {
            # Pre-reclaim (high priority)
            OperationalTransition.VOLUME_DRY_UP:        0.85,
            OperationalTransition.COMPRESSING:          0.80,
            OperationalTransition.FLUSH_AND_RECOVER:    0.80,
            OperationalTransition.SUPPORT_HOLDING:      0.75,
            OperationalTransition.ENTERING_PULLBACK:    0.70,
            # Pre-breakout (alta convicción)
            OperationalTransition.BREAKOUT:             0.85,
            # Reclaim / continuation (lowered from 0.80)
            OperationalTransition.RECLAIMING:           0.65,
            OperationalTransition.CONTINUATION_HOLDING: 0.60,
            # Deterioration
            OperationalTransition.FAILING:              0.95,
            OperationalTransition.DISTRIBUTION:         0.90,
            OperationalTransition.WEAKENING:            0.75,
            # Neutral
            OperationalTransition.STABILIZING:          0.50,
            OperationalTransition.STABLE:               0.40,
        }.get(transition, 0.50)

        # Magnitude adjustments
        if transition == OperationalTransition.VOLUME_DRY_UP:
            base += min(0.15, abs(volume_change_pct) / 200.0)
        elif transition == OperationalTransition.COMPRESSING:
            base += min(0.15, structure_change * 1.5)
        elif transition == OperationalTransition.BREAKOUT:
            base += min(0.10, structure_change * 1.5)  # más contracción de ATR = mejor
        elif transition == OperationalTransition.ENTERING_PULLBACK:
            base -= min(0.20, abs(rs_change) / 10.0)  # RS drop reduces quality

        return max(0.0, min(1.0, base))
    
    def _generate_operational_narrative(
        self,
        transition: OperationalTransition,
        rs_change: float,
        volume_change_pct: float,
        structure_change: float,
        current_metrics: StockMetrics
    ) -> str:
        """Short operational narrative focused on pre-reclaim context."""
        rvol = current_metrics.relative_volume or 1.0
        rs = current_metrics.relative_strength_spy or 0

        if transition == OperationalTransition.ENTERING_PULLBACK:
            ema9 = current_metrics.distance_to_ema9_atr or 999.0
            ema21 = current_metrics.distance_to_ema21_atr or 999.0
            if 0 < ema9 <= 0.5:
                return f"Approaching EMA9 — leader pulling back to fast EMA. Watch for support."
            elif 0 < ema21 <= 1.0:
                return f"Approaching EMA21 — leader testing key swing support. Controlled pullback."
            return "Leader approaching key EMA. Quality setup forming."

        narratives = {
            OperationalTransition.ENTERING_PULLBACK:    "Leader approaching key EMA. Quality setup forming.",
            OperationalTransition.VOLUME_DRY_UP:        f"Vol dry-up {volume_change_pct:.0f}%. Pre-setup forming.",
            OperationalTransition.COMPRESSING:          "Compressing. ATR contracting. Setup maturing.",
            OperationalTransition.FLUSH_AND_RECOVER:    "Undercut + recovery. Institutional level defended.",
            OperationalTransition.SUPPORT_HOLDING:      "Testing support. Holding. Watch for base.",
            OperationalTransition.BREAKOUT:             "Coiling cerca de máximos — volumen seco. Setup de breakout madurando.",
            OperationalTransition.RECLAIMING:           "Reclaiming EMA21. Late-stage signal.",
            OperationalTransition.CONTINUATION_HOLDING: f"Holding EMA21. RS {rs:.0f}.",
            OperationalTransition.WEAKENING:            f"Weakening. RS {rs_change:.1f}. Monitor closely.",
            OperationalTransition.DISTRIBUTION:         "Distribution. Volume expanding. Avoid.",
            OperationalTransition.FAILING:              "Failing. Structure lost. Exit.",
            OperationalTransition.STABILIZING:          "Stabilizing. No clear signal.",
            OperationalTransition.STABLE:               "Stable. Monitoring.",
        }
        return narratives.get(transition, "Monitoring.")
