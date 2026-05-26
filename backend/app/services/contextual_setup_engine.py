"""
Contextual Setup Engine — orchestrator.

Delegates each scoring concern to dedicated sub-modules:
  structure_scorer   — weekly structure, EMA health, volume behavior
  ma_analyzer        — slope, stacking, compression, expansion
  pullback_analyzer  — orderliness, volume dry-up, spread, support
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.models.stock import StockMetrics
from app.services.structure_scorer import score_structure_quality, evaluate_structure
from app.services.ma_analyzer import score_ma_context, analyze_ma_context
from app.services.pullback_analyzer import score_pullback_character, analyze_pullback_character

import logging

logger = logging.getLogger(__name__)


@dataclass
class SetupReadinessScore:
    """Comprehensive setup readiness score (0-100)"""
    total_score: float
    structure_quality: float
    volatility_compression: float
    rs_quality: float
    pullback_character: float
    ma_context: float
    market_alignment: float
    components: Dict[str, Any]


_REGIME_MULTIPLIERS: Dict[str, float] = {
    'risk_on':    1.00,
    'transition': 0.80,
    'choppy':     0.85,
    'risk_off':   0.65,
}


class ContextualSetupEngine:
    """
    Volatility-aware, structure-first setup scoring.

    Philosophy:
    - Structure > Distance
    - ATR-normalized distances throughout
    - Regime as a real multiplier on the base score
    """

    def __init__(self):
        pass

    def calculate_readiness_score(
        self,
        metrics: StockMetrics,
        market_regime: Optional[str] = None,
    ) -> SetupReadinessScore:
        structure_quality    = score_structure_quality(metrics)
        volatility_compr     = self._calculate_volatility_compression(metrics)
        rs_qual              = self._calculate_rs_quality(metrics)
        pullback_char        = score_pullback_character(metrics)
        ma_ctx               = score_ma_context(metrics)
        market_alignment     = self._calculate_market_alignment(metrics, market_regime)

        base_score = (
            structure_quality * 0.30 +
            volatility_compr  * 0.20 +
            rs_qual           * 0.20 +
            pullback_char     * 0.15 +
            ma_ctx            * 0.10
        )

        regime_mult = _REGIME_MULTIPLIERS.get(market_regime or '', 0.85)
        total_score = base_score * regime_mult

        components = {
            'structure_quality':    structure_quality,
            'volatility_compression': volatility_compr,
            'rs_quality':           rs_qual,
            'pullback_character':   pullback_char,
            'ma_context':           ma_ctx,
            'market_alignment':     market_alignment,
        }

        return SetupReadinessScore(
            total_score=min(100.0, max(0.0, total_score)),
            structure_quality=structure_quality,
            volatility_compression=volatility_compr,
            rs_quality=rs_qual,
            pullback_character=pullback_char,
            ma_context=ma_ctx,
            market_alignment=market_alignment,
            components=components,
        )

    def generate_readiness_narrative(self, score: SetupReadinessScore) -> str:
        parts = []
        parts.append("Structure strong" if score.structure_quality >= 70
                     else "Structure solid" if score.structure_quality >= 50
                     else "Structure weak")
        parts.append("Tight" if score.volatility_compression >= 70
                     else "Compressing" if score.volatility_compression >= 50
                     else "Loose")
        parts.append("RS strong" if score.rs_quality >= 70
                     else "RS solid" if score.rs_quality >= 50
                     else "RS weak")
        parts.append("Orderly pullback" if score.pullback_character >= 70
                     else "Constructive" if score.pullback_character >= 50
                     else "Impulsive")
        return ". ".join(parts) + "."

    # --- Delegating helpers for detailed analysis ---

    def evaluate_structure_first(self, metrics: StockMetrics) -> Dict[str, Any]:
        return evaluate_structure(metrics)

    def analyze_ma_context(self, metrics: StockMetrics) -> Dict[str, Any]:
        return analyze_ma_context(metrics)

    def analyze_pullback_character(self, metrics: StockMetrics) -> Dict[str, Any]:
        return analyze_pullback_character(metrics)

    # --- Scoring helpers that remain here (short, no natural home elsewhere) ---

    def _calculate_volatility_compression(self, metrics: StockMetrics) -> float:
        score = 0.0

        if metrics.volume_contraction:
            score += max(0.0, metrics.volume_contraction) * 40

        if metrics.weekly_volatility_contraction:
            score += max(0.0, metrics.weekly_volatility_contraction) * 30

        if metrics.distance_to_ema21_atr is not None:
            d = abs(metrics.distance_to_ema21_atr)
            if d <= 0.5:
                score += 30
            elif d <= 1.0:
                score += 20
            elif d <= 1.5:
                score += 10

        return min(100.0, max(0.0, score))

    def _calculate_rs_quality(self, metrics: StockMetrics) -> float:
        if not metrics.relative_strength_spy and not metrics.relative_strength_qqq:
            return 50.0

        score = 0.0

        if metrics.relative_strength_spy:
            rs = metrics.relative_strength_spy
            score += 50 if rs >= 110 else 40 if rs >= 105 else 30 if rs >= 100 else 15 if rs >= 95 else 0

        if metrics.relative_strength_qqq:
            rq = metrics.relative_strength_qqq
            score += 50 if rq >= 110 else 40 if rq >= 105 else 30 if rq >= 100 else 15 if rq >= 95 else 0

        return min(100.0, score)

    def _calculate_market_alignment(
        self,
        metrics: StockMetrics,
        market_regime: Optional[str],
    ) -> float:
        if not market_regime:
            return 50.0
        return {'risk_on': 80.0, 'risk_off': 30.0, 'choppy': 40.0}.get(market_regime, 50.0)
