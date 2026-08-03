"""Setup Lifecycle Engine — Pre-reclaim intelligence model.

Philosophy:
- RECLAIM is the consequence, not the setup.
- The setup is born in PREPARATION: compression, reset, flush, tightening.
- Losing EMA is NOT automatically bearish — it often begins the next setup.
- Structure > EMA location.
- Volume dry-up below EMA > reclaim on volume.
"""

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stock import StockMetrics
from app.services.empirical_probability_calculator import EmpiricalProbabilityCalculator
import logging

logger = logging.getLogger(__name__)


class SetupState(Enum):
    """
    Lifecycle states — pre-reclaim states are the operational focus.

    PRE-RECLAIM (primary focus):
      EARLY_PULLBACK, CONTROLLED_PULLBACK, VOLATILITY_CONTRACTION,
      TIGHTENING, UNDERCUT, SUPPORT_TESTING

    RECLAIM (exist, not the focus):
      RECLAIM_PREPARATION, RECLAIM_IN_PROGRESS

    CONTINUATION (tracking open positions):
      CONTINUATION

    DETERIORATION:
      DISTRIBUTION, BROKEN
    """
    # Pre-reclaim (foco operacional)
    EARLY_PULLBACK         = "early_pullback"
    CONTROLLED_PULLBACK    = "controlled_pullback"
    VOLATILITY_CONTRACTION = "volatility_contraction"
    TIGHTENING             = "tightening"
    UNDERCUT               = "undercut"
    SUPPORT_TESTING        = "support_testing"

    # Reclaim (existen, no son el foco)
    RECLAIM_PREPARATION    = "reclaim_preparation"
    RECLAIM_IN_PROGRESS    = "reclaim_in_progress"

    # Continuation
    CONTINUATION           = "continuation"

    # Deterioration
    DISTRIBUTION           = "distribution"
    BROKEN                 = "broken"


@dataclass
class StateTransition:
    from_state: SetupState
    to_state: SetupState
    timestamp: datetime
    quality_score: float
    structural_health: float


class SetupLifecycleEngine:
    """
    Engine to detect and track the lifecycle of institutional setups.

    Detection priority order:
    1. Broken / Distribution (eliminate)
    2. Continuation (track open positions)
    3. Reclaim states (late-stage, exist for completeness)
    4. PRE-RECLAIM states (the operational focus)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def detect_current_state(self, metrics: StockMetrics) -> SetupState:
        """Detect current state. Structure-first, location-second."""
        if self._is_broken(metrics):
            return SetupState.BROKEN

        if self._is_distribution(metrics):
            return SetupState.DISTRIBUTION

        if self._is_continuation(metrics):
            return SetupState.CONTINUATION

        if self._is_reclaim_in_progress(metrics):
            return SetupState.RECLAIM_IN_PROGRESS

        if self._is_reclaim_preparation(metrics):
            return SetupState.RECLAIM_PREPARATION

        # === PRE-RECLAIM STATES — operational focus ===

        if self._is_undercut(metrics):
            return SetupState.UNDERCUT

        if self._is_support_testing(metrics):
            return SetupState.SUPPORT_TESTING

        if self._is_tightening(metrics):
            return SetupState.TIGHTENING

        if self._is_volatility_contraction(metrics):
            return SetupState.VOLATILITY_CONTRACTION

        if self._is_controlled_pullback(metrics):
            return SetupState.CONTROLLED_PULLBACK

        return SetupState.EARLY_PULLBACK

    def detect_state_transition(
        self,
        symbol: str,
        old_state: SetupState,
        new_state: SetupState,
    ) -> Optional[StateTransition]:
        if old_state == new_state:
            return None
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            timestamp=datetime.now(),
            quality_score=0.0,
            structural_health=0.0,
        )
        logger.info(f"State transition {symbol}: {old_state.value} → {new_state.value}")
        return transition

    def _rule_based_probability(self, metrics: StockMetrics) -> float:
        """Weighted-composite formula (unchanged fallback)."""
        probability = 0.0
        if metrics.weekly_trend_quality:
            probability += metrics.weekly_trend_quality * 0.40
        if metrics.pullback_quality_score:
            probability += min(1.0, metrics.pullback_quality_score / 100.0) * 0.30
        if metrics.relative_strength_spy:
            rs = metrics.relative_strength_spy
            if rs >= 115:   probability += 0.20
            elif rs >= 110: probability += 0.16
            elif rs >= 105: probability += 0.12
            elif rs >= 100: probability += 0.08
            elif rs >= 95:  probability += 0.04
        if metrics.volume_contraction and metrics.volume_contraction > 0:
            probability += min(0.10, metrics.volume_contraction * 0.10)
        return min(1.0, max(0.0, probability))

    async def calculate_continuation_probability(
        self,
        metrics: StockMetrics,
        transition_type: Optional[str] = None,
        current_regime: Optional[str] = None,
    ) -> tuple[float, str, int, str]:
        """
        Returns (probability, source, sample_size, empirical_basis).

        Tries empirical lookup first (when transition_type is known).
        Falls back to rule-based weighted-composite formula.
        """
        if transition_type:
            try:
                calc = EmpiricalProbabilityCalculator(self.db)
                emp = await calc.lookup(
                    transition_type,
                    metrics.relative_strength_spy,
                    current_regime=current_regime,
                    as_of_date=metrics.date,
                )
                if emp.source == 'empirical':
                    return (
                        round(emp.probability, 4),
                        'empirical',
                        emp.sample_size,
                        emp.basis,
                    )
            except Exception as e:
                logger.warning(f"Empirical lookup failed, using rule-based: {e}")

        return (
            round(self._rule_based_probability(metrics), 4),
            'rule_based',
            0,
            'rule_formula',
        )

    def generate_narrative(self, metrics: StockMetrics, state: SetupState) -> str:
        """Short operational narrative."""
        weeks_base = metrics.weeks_in_base or 0
        pullback_score = metrics.pullback_quality_score or 0
        rs_spy = metrics.relative_strength_spy or 0
        cont_prob = self._rule_based_probability(metrics)

        narratives = {
            SetupState.EARLY_PULLBACK:         "Lost EMA. Structure intact. Begin monitoring.",
            SetupState.CONTROLLED_PULLBACK:    "Controlled reset. Vol dry-up. EMA50 rising.",
            SetupState.VOLATILITY_CONTRACTION: "Volatility compressing. Setup forming.",
            SetupState.TIGHTENING:             f"Tightening {weeks_base}w. Weak hands out.",
            SetupState.UNDERCUT:               "Undercut EMA50. Watch for recovery.",
            SetupState.SUPPORT_TESTING:        "Testing EMA50 support. Key zone.",
            SetupState.RECLAIM_PREPARATION:    f"Pre-reclaim. Score: {pullback_score:.0f}. Prob: {cont_prob:.0%}.",
            SetupState.RECLAIM_IN_PROGRESS:    f"Reclaiming EMA21. Late-stage. RS: {rs_spy:.0f}.",
            SetupState.CONTINUATION:           f"Continuation. Holding EMA21. RS: {rs_spy:.0f}.",
            SetupState.DISTRIBUTION:           "Distribution. Volume expanding. Avoid.",
            SetupState.BROKEN:                 "Broken. Structure failed. No longer valid.",
        }
        return narratives.get(state, "Monitoring.")

    # ─── Helper methods ───────────────────────────────────────────────────────

    def _is_broken(self, metrics: StockMetrics) -> bool:
        if metrics.distance_to_ema50_atr is None:
            return False
        return metrics.distance_to_ema50_atr < -2.5

    def _is_distribution(self, metrics: StockMetrics) -> bool:
        """EMA21 lost + volume expanding + RS collapsing = real distribution."""
        if metrics.distance_to_ema21_atr is None:
            return False
        ema21_lost = metrics.distance_to_ema21_atr < -0.8
        volume_expanding = (metrics.relative_volume is not None and
                            metrics.relative_volume > 1.3)
        rs_weak = (metrics.relative_strength_spy is not None and
                   metrics.relative_strength_spy < 95)
        return ema21_lost and volume_expanding and rs_weak

    def _is_continuation(self, metrics: StockMetrics) -> bool:
        return (metrics.distance_to_ema21_atr is not None and
                0 <= metrics.distance_to_ema21_atr <= 1.5 and
                metrics.weekly_trend_quality is not None and
                metrics.weekly_trend_quality > 0.7)

    def _is_reclaim_in_progress(self, metrics: StockMetrics) -> bool:
        """Very close to EMA21 from below — already late for ideal entry."""
        return (metrics.distance_to_ema21_atr is not None and
                -0.5 <= metrics.distance_to_ema21_atr < -0.05)

    def _is_reclaim_preparation(self, metrics: StockMetrics) -> bool:
        """0.5–1.0 ATR below EMA21, high pullback quality — about to reclaim."""
        return (metrics.distance_to_ema21_atr is not None and
                -1.0 <= metrics.distance_to_ema21_atr < -0.5 and
                metrics.pullback_quality_score is not None and
                metrics.pullback_quality_score >= 65)

    def _is_undercut(self, metrics: StockMetrics) -> bool:
        """Constructive EMA50 flush: near EMA50 + volume spike."""
        if metrics.distance_to_ema50_atr is None:
            return False
        near_ema50 = -2.5 <= metrics.distance_to_ema50_atr <= -0.3
        vol_spike = (metrics.relative_volume is not None and
                     metrics.relative_volume > 1.4)
        return near_ema50 and vol_spike

    def _is_support_testing(self, metrics: StockMetrics) -> bool:
        """Testing EMA50 zone (-0.5 to +0.2 ATR) with EMA21 already lost."""
        return (metrics.distance_to_ema50_atr is not None and
                -0.5 <= metrics.distance_to_ema50_atr <= 0.2 and
                metrics.distance_to_ema21_atr is not None and
                metrics.distance_to_ema21_atr < -0.8)

    def _is_tightening(self, metrics: StockMetrics) -> bool:
        """Multiple tight weeks with volume contraction — weak hands flushed."""
        return (metrics.weekly_tightness is not None and
                metrics.weekly_tightness > 0.6 and
                metrics.volume_contraction is not None and
                metrics.volume_contraction > 0.3)

    def _is_volatility_contraction(self, metrics: StockMetrics) -> bool:
        """ATR compressing actively below EMAs — setup maturing."""
        return (metrics.weekly_volatility_contraction is not None and
                metrics.weekly_volatility_contraction > 0.4 and
                metrics.distance_to_ema21_atr is not None and
                metrics.distance_to_ema21_atr < -0.3)

    def _is_controlled_pullback(self, metrics: StockMetrics) -> bool:
        """Orderly 1–3.5 ATR below EMA21, EMA50 healthy, low volume."""
        if metrics.distance_to_ema21_atr is None:
            return False
        in_range = -3.5 <= metrics.distance_to_ema21_atr < -1.0
        ema50_ok = (metrics.distance_to_ema50_atr is not None and
                    metrics.distance_to_ema50_atr > -1.5)
        low_vol = (metrics.relative_volume is None or
                   metrics.relative_volume < 1.2)
        return in_range and ema50_ok and low_vol
