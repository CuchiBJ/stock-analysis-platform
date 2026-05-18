"""Weekly Structure Calculator - Rule-based scoring engine for weekly base quality"""

from dataclasses import dataclass
from typing import Optional
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeeklyStructureScore:
    """Score and breakdown of weekly structure quality"""
    total_score: float
    base_duration_score: float
    weekly_tightness_score: float
    volatility_contraction_score: float
    distance_to_highs_score: float
    rs_consistency_score: float
    pullback_quality_score: float
    trend_alignment_score: float
    ema21_respect_score: float
    volume_contraction_score: float
    
    def get_breakdown(self) -> dict:
        """Get detailed breakdown of scores"""
        return {
            "total_score": self.total_score,
            "base_duration": self.base_duration_score,
            "weekly_tightness": self.weekly_tightness_score,
            "volatility_contraction": self.volatility_contraction_score,
            "distance_to_highs": self.distance_to_highs_score,
            "rs_consistency": self.rs_consistency_score,
            "pullback_quality": self.pullback_quality_score,
            "trend_alignment": self.trend_alignment_score,
            "ema21_respect": self.ema21_respect_score,
            "volume_contraction": self.volume_contraction_score
        }


class WeeklyStructureCalculator:
    """
    Rule-based scoring engine for weekly base quality.
    
    Core philosophy: Structure-first scanning. Prioritize weekly structure
    quality over momentum or hype. This reflects institutional trading patterns
    where structure and continuation are more important than short-term moves.
    
    Scoring based on:
    - Base duration (4-8 weeks optimal)
    - Weekly tight closes (>70% tight optimal)
    - Volatility contraction (>50% optimal)
    - Distance to highs (<15% optimal)
    - RS consistency (stable or improving)
    - Pullback quality
    - Trend alignment
    - EMA21 respect
    - Volume contraction
    """
    
    def __init__(self):
        pass
    
    def calculate_weekly_structure_score(self, metrics: StockMetrics) -> WeeklyStructureScore:
        """
        Calculate comprehensive weekly structure score.
        
        Returns a score from 0-100 based on multiple structural factors.
        This is rule-based for interpretability and rapid iteration.
        """
        scores = WeeklyStructureScore(
            total_score=0.0,
            base_duration_score=self._score_base_duration(metrics),
            weekly_tightness_score=self._score_weekly_tightness(metrics),
            volatility_contraction_score=self._score_volatility_contraction(metrics),
            distance_to_highs_score=self._score_distance_to_highs(metrics),
            rs_consistency_score=self._score_rs_consistency(metrics),
            pullback_quality_score=self._score_pullback_quality(metrics),
            trend_alignment_score=self._score_trend_alignment(metrics),
            ema21_respect_score=self._score_ema21_respect(metrics),
            volume_contraction_score=self._score_volume_contraction(metrics)
        )
        
        # Calculate total score (weighted average)
        # Weights reflect importance of each factor
        weights = {
            "base_duration": 0.15,
            "weekly_tightness": 0.15,
            "volatility_contraction": 0.10,
            "distance_to_highs": 0.10,
            "rs_consistency": 0.10,
            "pullback_quality": 0.15,
            "trend_alignment": 0.10,
            "ema21_respect": 0.10,
            "volume_contraction": 0.05
        }
        
        scores.total_score = (
            scores.base_duration_score * weights["base_duration"] +
            scores.weekly_tightness_score * weights["weekly_tightness"] +
            scores.volatility_contraction_score * weights["volatility_contraction"] +
            scores.distance_to_highs_score * weights["distance_to_highs"] +
            scores.rs_consistency_score * weights["rs_consistency"] +
            scores.pullback_quality_score * weights["pullback_quality"] +
            scores.trend_alignment_score * weights["trend_alignment"] +
            scores.ema21_respect_score * weights["ema21_respect"] +
            scores.volume_contraction_score * weights["volume_contraction"]
        )
        
        return scores
    
    def _score_base_duration(self, metrics: StockMetrics) -> float:
        """
        Score base duration (4-8 weeks optimal).
        
        Bases that are too short (<4 weeks) lack structure.
        Bases that are too long (>12 weeks) may be stale.
        """
        if not metrics.weeks_in_base:
            return 0.0
        
        weeks = metrics.weeks_in_base
        
        if 4 <= weeks <= 8:
            return 100.0  # Optimal
        elif 3 <= weeks <= 10:
            return 80.0   # Good
        elif 2 <= weeks <= 12:
            return 60.0   # Fair
        elif weeks < 2:
            return 30.0   # Too short
        else:  # weeks > 12
            return 40.0   # Too long, potentially stale
    
    def _score_weekly_tightness(self, metrics: StockMetrics) -> float:
        """
        Score weekly tight closes (>70% tight optimal).
        
        Tight weekly closes indicate institutional accumulation
        and controlled supply.
        """
        if not metrics.weekly_tightness:
            return 0.0
        
        tightness = metrics.weekly_tightness
        
        if tightness >= 0.7:
            return 100.0  # Excellent
        elif tightness >= 0.6:
            return 80.0   # Good
        elif tightness >= 0.5:
            return 60.0   # Fair
        elif tightness >= 0.4:
            return 40.0   # Poor
        else:
            return 20.0   # Very poor
    
    def _score_volatility_contraction(self, metrics: StockMetrics) -> float:
        """
        Score volatility contraction (>50% optimal).
        
        Volatility contraction indicates supply absorption
        and institutional control.
        """
        if not metrics.weekly_volatility_contraction:
            return 0.0
        
        contraction = metrics.weekly_volatility_contraction
        
        if contraction >= 0.5:
            return 100.0  # Excellent
        elif contraction >= 0.4:
            return 80.0   # Good
        elif contraction >= 0.3:
            return 60.0   # Fair
        elif contraction >= 0.2:
            return 40.0   # Poor
        else:
            return 20.0   # Very poor
    
    def _score_distance_to_highs(self, metrics: StockMetrics) -> float:
        """
        Score distance to highs (<15% from ATH optimal).
        
        Close to highs indicates strength and continuation potential.
        """
        if not metrics.distance_to_high_52w:
            return 0.0
        
        dist_to_high = metrics.distance_to_high_52w
        
        if dist_to_high >= -5:
            return 100.0  # Excellent - within 5% of ATH
        elif dist_to_high >= -10:
            return 80.0   # Good - within 10% of ATH
        elif dist_to_high >= -15:
            return 60.0   # Fair - within 15% of ATH
        elif dist_to_high >= -20:
            return 40.0   # Poor - within 20% of ATH
        else:
            return 20.0   # Very poor - more than 20% from ATH
    
    def _score_rs_consistency(self, metrics: StockMetrics) -> float:
        """
        Score RS consistency (stable or improving vs SPY).
        
        Consistent RS indicates institutional leadership.
        """
        if not metrics.relative_strength_spy:
            return 0.0
        
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
    
    def _score_pullback_quality(self, metrics: StockMetrics) -> float:
        """
        Score pullback quality (from existing pullback quality score).
        
        Reuse the existing pullback quality score as a component.
        """
        if not metrics.pullback_quality_score:
            return 0.0
        
        return metrics.pullback_quality_score
    
    def _score_trend_alignment(self, metrics: StockMetrics) -> float:
        """
        Score trend alignment (price > EMA50 and EMA50 > EMA200).
        
        Trend alignment indicates continuation setup.
        """
        if metrics.distance_to_ema50 is None:
            return 0.0
        
        if metrics.distance_to_ema50 >= 0:
            return 100.0  # Excellent - above EMA50
        elif metrics.distance_to_ema50 >= -5:
            return 60.0   # Fair - near EMA50
        else:
            return 20.0   # Poor - below EMA50
    
    def _score_ema21_respect(self, metrics: StockMetrics) -> float:
        """
        Score EMA21 respect (price near or above EMA21).
        
        EMA21 respect indicates healthy pullback zone.
        """
        if metrics.distance_to_ema21 is None:
            return 0.0
        
        dist = metrics.distance_to_ema21
        
        if 0 <= dist <= 5:
            return 100.0  # Excellent - in optimal pullback zone
        elif -5 <= dist <= 10:
            return 80.0   # Good - near pullback zone
        elif -10 <= dist <= 15:
            return 60.0   # Fair - deeper pullback
        else:
            return 40.0   # Poor - too deep or too extended
    
    def _score_volume_contraction(self, metrics: StockMetrics) -> float:
        """
        Score volume contraction during pullback.
        
        Volume contraction indicates supply absorption.
        """
        if not metrics.volume_contraction:
            return 0.0
        
        contraction = metrics.volume_contraction
        
        if contraction >= 0.5:
            return 100.0  # Excellent - strong contraction
        elif contraction >= 0.3:
            return 80.0   # Good - moderate contraction
        elif contraction >= 0.1:
            return 60.0   # Fair - some contraction
        else:
            return 40.0   # Poor - no contraction or expansion
