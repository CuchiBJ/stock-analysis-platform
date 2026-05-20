"""
Contextual Setup Engine - Volatility-aware, structure-first scoring.

This engine provides sophisticated setup evaluation that considers:
- Individual volatility profile (ATR-normalized)
- Structure integrity over absolute distance
- Volatility compression patterns
- RS behavior and quality
- MA contextual analysis
- Pullback character and orderliness
- Market regime alignment

Designed for institutional momentum trading logic.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from app.models.stock import StockMetrics
import logging

logger = logging.getLogger(__name__)


@dataclass
class SetupReadinessScore:
    """Comprehensive setup readiness score (0-100)"""
    total_score: float
    structure_quality: float  # 0-100
    volatility_compression: float  # 0-100
    rs_quality: float  # 0-100
    pullback_character: float  # 0-100
    ma_context: float  # 0-100
    market_alignment: float  # 0-100
    
    # Component breakdown for explainability
    components: Dict[str, Any]


class ContextualSetupEngine:
    """
    Engine for contextual, volatility-aware setup scoring.
    
    Philosophy:
    - Structure > Distance
    - Volatility-aware positioning
    - Contextual compression analysis
    - Institutional-grade interpretability
    """
    
    def __init__(self):
        pass
    
    def calculate_readiness_score(
        self,
        metrics: StockMetrics,
        market_regime: Optional[str] = None
    ) -> SetupReadinessScore:
        """
        Calculate comprehensive setup readiness score.
        
        Scoring weights (institutional momentum logic):
        - Structure quality: 30%
        - Volatility compression: 20%
        - RS quality: 20%
        - Pullback character: 15%
        - MA context: 10%
        - Market alignment: 5%
        """
        # Calculate individual components
        structure_quality = self._calculate_structure_quality(metrics)
        volatility_compression = self._calculate_volatility_compression(metrics)
        rs_quality = self._calculate_rs_quality(metrics)
        pullback_character = self._calculate_pullback_character(metrics)
        ma_context = self._calculate_ma_context(metrics)
        market_alignment = self._calculate_market_alignment(metrics, market_regime)
        
        # Weighted composite score
        total_score = (
            structure_quality * 0.30 +
            volatility_compression * 0.20 +
            rs_quality * 0.20 +
            pullback_character * 0.15 +
            ma_context * 0.10 +
            market_alignment * 0.05
        )
        
        components = {
            "structure_quality": structure_quality,
            "volatility_compression": volatility_compression,
            "rs_quality": rs_quality,
            "pullback_character": pullback_character,
            "ma_context": ma_context,
            "market_alignment": market_alignment
        }
        
        return SetupReadinessScore(
            total_score=min(100.0, max(0.0, total_score)),
            structure_quality=structure_quality,
            volatility_compression=volatility_compression,
            rs_quality=rs_quality,
            pullback_character=pullback_character,
            ma_context=ma_context,
            market_alignment=market_alignment,
            components=components
        )
    
    def _calculate_structure_quality(self, metrics: StockMetrics) -> float:
        """
        Calculate structure quality score (0-100).
        
        Structure quality evaluates:
        - Weekly trend quality
        - Weekly tightness
        - Weeks in base
        - Setup quality
        
        Structure > Distance: A setup can be excellent even if not at EMA
        if weekly structure is intact and tightening.
        """
        score = 0.0
        
        # Weekly trend quality (40 points)
        if metrics.weekly_trend_quality:
            score += metrics.weekly_trend_quality * 40
        
        # Weekly tightness (30 points)
        if metrics.weekly_tightness:
            score += metrics.weekly_tightness * 30
        
        # Setup quality (20 points)
        if metrics.setup_quality:
            if metrics.setup_quality == 'excellent':
                score += 20
            elif metrics.setup_quality == 'good':
                score += 15
            elif metrics.setup_quality == 'fair':
                score += 10
        
        # Weeks in base (10 points) - sweet spot 4-12 weeks
        if metrics.weeks_in_base:
            if 4 <= metrics.weeks_in_base <= 12:
                score += 10
            elif 2 <= metrics.weeks_in_base < 4:
                score += 5
            elif metrics.weeks_in_base > 12:
                score += 7  # Extended base still valid
        
        return min(100.0, score)
    
    def _calculate_volatility_compression(self, metrics: StockMetrics) -> float:
        """
        Calculate volatility compression score (0-100).
        
        Volatility compression evaluates:
        - Volume contraction
        - Weekly volatility contraction
        - ATR positioning (contextual)
        
        Tightness matters more than absolute distance.
        """
        score = 0.0
        
        # Volume contraction (40 points)
        if metrics.volume_contraction:
            # Normalize 0-1 to 0-40, ensure non-negative
            contraction_score = max(0.0, metrics.volume_contraction) * 40
            score += contraction_score
        
        # Weekly volatility contraction (30 points)
        if metrics.weekly_volatility_contraction:
            contraction_score = max(0.0, metrics.weekly_volatility_contraction) * 30
            score += contraction_score
        
        # ATR positioning - contextual compression (30 points)
        if metrics.distance_to_ema21_atr is not None:
            # Within 0.5 ATR of EMA21 = high compression
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 30
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 20
            elif abs(metrics.distance_to_ema21_atr) <= 1.5:
                score += 10
        
        return min(100.0, max(0.0, score))
    
    def _calculate_rs_quality(self, metrics: StockMetrics) -> float:
        """
        Calculate RS quality score (0-100).
        
        RS quality evaluates:
        - Relative strength vs SPY
        - Relative strength vs QQQ
        - RS holding vs deteriorating
        """
        score = 0.0
        
        # If RS metrics are not available, return neutral score
        if not metrics.relative_strength_spy and not metrics.relative_strength_qqq:
            return 50.0  # Neutral score when RS data unavailable
        
        # RS vs SPY (50 points)
        if metrics.relative_strength_spy:
            if metrics.relative_strength_spy >= 110:
                score += 50
            elif metrics.relative_strength_spy >= 105:
                score += 40
            elif metrics.relative_strength_spy >= 100:
                score += 30
            elif metrics.relative_strength_spy >= 95:
                score += 15
        
        # RS vs QQQ (50 points)
        if metrics.relative_strength_qqq:
            if metrics.relative_strength_qqq >= 110:
                score += 50
            elif metrics.relative_strength_qqq >= 105:
                score += 40
            elif metrics.relative_strength_qqq >= 100:
                score += 30
            elif metrics.relative_strength_qqq >= 95:
                score += 15
        
        return min(100.0, score)
    
    def _calculate_pullback_character(self, metrics: StockMetrics) -> float:
        """
        Calculate pullback character score (0-100).
        
        Pullback character evaluates:
        - Pullback quality score
        - Orderliness (using ATR-normalized positioning)
        - Support reaction context
        """
        score = 0.0
        
        # Pullback quality score (60 points)
        if metrics.pullback_quality_score:
            # Normalize 0-100 to 0-60
            score += min(60.0, metrics.pullback_quality_score * 0.6)
        
        # Orderliness - ATR-normalized positioning (40 points)
        if metrics.distance_to_ema21_atr is not None:
            # Orderly pullback: 0.5-2.0 ATRs below EMA21
            if -2.0 <= metrics.distance_to_ema21_atr <= -0.5:
                score += 40
            elif -3.0 <= metrics.distance_to_ema21_atr < -2.0:
                score += 25
            elif -0.5 < metrics.distance_to_ema21_atr <= 0.5:
                score += 30  # Near EMA but not extended
        
        return min(100.0, score)
    
    def _calculate_ma_context(self, metrics: StockMetrics) -> float:
        """
        Calculate MA context score (0-100).
        
        MA context evaluates:
        - EMA alignment
        - Distance to EMAs (ATR-normalized)
        - Trend health
        """
        score = 0.0
        
        # EMA alignment (40 points)
        # Check if price > EMA21 > EMA50 > EMA200
        if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
                score += 40
            elif metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= -5:
                score += 25
        
        # ATR-normalized positioning (60 points)
        if metrics.distance_to_ema21_atr is not None:
            # Within 1 ATR of EMA21 = good context
            if abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 60
            elif abs(metrics.distance_to_ema21_atr) <= 2.0:
                score += 40
            elif abs(metrics.distance_to_ema21_atr) <= 3.0:
                score += 20
        
        return min(100.0, score)
    
    def _calculate_market_alignment(
        self,
        metrics: StockMetrics,
        market_regime: Optional[str]
    ) -> float:
        """
        Calculate market alignment score (0-100).
        
        Market alignment evaluates:
        - Market regime compatibility
        - Sector context (if available)
        """
        score = 50.0  # Base score (neutral)
        
        if market_regime:
            if market_regime == "risk_on":
                score = 80.0  # Favorable for momentum
            elif market_regime == "risk_off":
                score = 30.0  # Unfavorable
            elif market_regime == "choppy":
                score = 40.0  # Difficult environment
        
        return score
    
    def generate_readiness_narrative(self, score: SetupReadinessScore) -> str:
        """
        Generate explanatory narrative for readiness score.
        
        Provides operational explainability.
        """
        components = []
        
        # Structure quality
        if score.structure_quality >= 70:
            components.append("Structure strong")
        elif score.structure_quality >= 50:
            components.append("Structure solid")
        else:
            components.append("Structure weak")
        
        # Volatility compression
        if score.volatility_compression >= 70:
            components.append("Tight")
        elif score.volatility_compression >= 50:
            components.append("Compressing")
        else:
            components.append("Loose")
        
        # RS quality
        if score.rs_quality >= 70:
            components.append("RS strong")
        elif score.rs_quality >= 50:
            components.append("RS solid")
        else:
            components.append("RS weak")
        
        # Pullback character
        if score.pullback_character >= 70:
            components.append("Orderly pullback")
        elif score.pullback_character >= 50:
            components.append("Constructive")
        else:
            components.append("Impulsive")
        
        return ". ".join(components) + "."
    
    def evaluate_structure_first(
        self,
        metrics: StockMetrics
    ) -> Dict[str, Any]:
        """
        Structure-first evaluation - assess structure integrity beyond absolute distance.
        
        Philosophy:
        - Structure > Distance
        - A setup can be excellent even if not at EMA if weekly structure is intact
        - Volume dry-up, RS holding, EMA rising, tightness increasing matter more
        - Volatility compression indicates operational readiness
        
        Returns:
        - structure_integrity: Overall structure health (0-100)
        - structure_health: Detailed breakdown
        - is_actionable: Whether setup is operationally actionable
        - rationale: Explanation of structure assessment
        """
        structure_health = {}
        
        # 1. Weekly structure integrity
        weekly_integrity = self._evaluate_weekly_structure(metrics)
        structure_health['weekly_integrity'] = weekly_integrity
        
        # 2. Volume behavior
        volume_health = self._evaluate_volume_behavior(metrics)
        structure_health['volume_health'] = volume_health
        
        # 3. RS holding pattern
        rs_health = self._evaluate_rs_holding(metrics)
        structure_health['rs_health'] = rs_health
        
        # 4. EMA slope and health
        ema_health = self._evaluate_ema_health(metrics)
        structure_health['ema_health'] = ema_health
        
        # 5. Volatility compression
        volatility_health = self._evaluate_volatility_health(metrics)
        structure_health['volatility_health'] = volatility_health
        
        # Calculate overall structure integrity
        structure_integrity = (
            weekly_integrity['score'] * 0.30 +
            volume_health['score'] * 0.20 +
            rs_health['score'] * 0.20 +
            ema_health['score'] * 0.15 +
            volatility_health['score'] * 0.15
        )
        
        # Determine if actionable
        is_actionable = self._is_structure_actionable(
            structure_integrity,
            structure_health
        )
        
        # Generate rationale
        rationale = self._generate_structure_rationale(
            structure_integrity,
            structure_health,
            is_actionable
        )
        
        return {
            'structure_integrity': min(100.0, max(0.0, structure_integrity)),
            'structure_health': structure_health,
            'is_actionable': is_actionable,
            'rationale': rationale
        }
    
    def _evaluate_weekly_structure(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Evaluate weekly structure integrity"""
        score = 0.0
        factors = []
        
        # Weekly trend quality
        if metrics.weekly_trend_quality:
            if metrics.weekly_trend_quality >= 0.7:
                score += 40
                factors.append("Strong weekly trend")
            elif metrics.weekly_trend_quality >= 0.5:
                score += 25
                factors.append("Solid weekly trend")
            elif metrics.weekly_trend_quality >= 0.3:
                score += 10
                factors.append("Weak weekly trend")
        
        # Weekly tightness
        if metrics.weekly_tightness:
            if metrics.weekly_tightness >= 0.6:
                score += 30
                factors.append("Tight weekly structure")
            elif metrics.weekly_tightness >= 0.4:
                score += 15
                factors.append("Moderate tightness")
        
        # Weeks in base
        if metrics.weeks_in_base:
            if 4 <= metrics.weeks_in_base <= 12:
                score += 30
                factors.append("Optimal base length")
            elif 2 <= metrics.weeks_in_base < 4:
                score += 15
                factors.append("Early base")
            elif metrics.weeks_in_base > 12:
                score += 20
                factors.append("Extended base")
        
        return {
            'score': score,
            'factors': factors
        }
    
    def _evaluate_volume_behavior(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Evaluate volume behavior and dry-up pattern"""
        score = 0.0
        factors = []
        
        # Volume contraction
        if metrics.volume_contraction:
            if metrics.volume_contraction >= 0.7:
                score += 50
                factors.append("Strong volume dry-up")
            elif metrics.volume_contraction >= 0.5:
                score += 35
                factors.append("Moderate volume dry-up")
            elif metrics.volume_contraction >= 0.3:
                score += 15
                factors.append("Some volume contraction")
        
        # Average volume (liquidity)
        if metrics.avg_volume_10d:
            if metrics.avg_volume_10d >= 1000000:
                score += 50
                factors.append("High liquidity")
            elif metrics.avg_volume_10d >= 500000:
                score += 30
                factors.append("Good liquidity")
            elif metrics.avg_volume_10d >= 200000:
                score += 10
                factors.append("Adequate liquidity")
        
        return {
            'score': score,
            'factors': factors
        }
    
    def _evaluate_rs_holding(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Evaluate RS holding pattern"""
        score = 0.0
        factors = []
        
        # If RS data not available, give neutral score
        if not metrics.relative_strength_spy and not metrics.relative_strength_qqq:
            return {
                'score': 50.0,
                'factors': ["RS data unavailable"]
            }
        
        # RS vs SPY
        if metrics.relative_strength_spy:
            if metrics.relative_strength_spy >= 105:
                score += 50
                factors.append("Strong RS vs SPY")
            elif metrics.relative_strength_spy >= 100:
                score += 35
                factors.append("Solid RS vs SPY")
            elif metrics.relative_strength_spy >= 95:
                score += 15
                factors.append("Weak RS vs SPY")
        
        # RS vs QQQ
        if metrics.relative_strength_qqq:
            if metrics.relative_strength_qqq >= 105:
                score += 50
                factors.append("Strong RS vs QQQ")
            elif metrics.relative_strength_qqq >= 100:
                score += 35
                factors.append("Solid RS vs QQQ")
            elif metrics.relative_strength_qqq >= 95:
                score += 15
                factors.append("Weak RS vs QQQ")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _evaluate_ema_health(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Evaluate EMA slope and health"""
        score = 0.0
        factors = []
        
        # EMA alignment (price > EMA21 > EMA50)
        if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
                score += 40
                factors.append("EMA alignment bullish")
            elif metrics.distance_to_ema21 >= 0:
                score += 25
                factors.append("Above EMA21")
        
        # ATR-normalized positioning (contextual)
        if metrics.distance_to_ema21_atr is not None:
            if abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 30
                factors.append("Near EMA21 (ATR-normalized)")
            elif abs(metrics.distance_to_ema21_atr) <= 2.0:
                score += 15
                factors.append("Within 2 ATRs of EMA21")
        
        # EMA50 health
        if metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema50 >= 0:
                score += 30
                factors.append("Above EMA50")
            elif metrics.distance_to_ema50 >= -5:
                score += 15
                factors.append("Near EMA50")
        
        return {
            'score': score,
            'factors': factors
        }
    
    def _evaluate_volatility_health(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Evaluate volatility compression and health"""
        score = 0.0
        factors = []
        
        # Weekly volatility contraction
        if metrics.weekly_volatility_contraction:
            if metrics.weekly_volatility_contraction >= 0.6:
                score += 40
                factors.append("Strong volatility contraction")
            elif metrics.weekly_volatility_contraction >= 0.4:
                score += 25
                factors.append("Moderate volatility contraction")
        
        # ATR positioning
        if metrics.distance_to_ema21_atr is not None:
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 30
                factors.append("Tight to EMA21")
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 20
                factors.append("Near EMA21")
        
        # ADR (Average Daily Range)
        if metrics.adr_percent:
            if metrics.adr_percent <= 5:
                score += 30
                factors.append("Low volatility")
            elif metrics.adr_percent <= 10:
                score += 15
                factors.append("Moderate volatility")
        
        return {
            'score': score,
            'factors': factors
        }
    
    def _is_structure_actionable(
        self,
        structure_integrity: float,
        structure_health: Dict[str, Any]
    ) -> bool:
        """Determine if structure is operationally actionable"""
        # Minimum structure integrity
        if structure_integrity < 50:
            return False
        
        # Must have solid weekly structure
        if structure_health['weekly_integrity']['score'] < 40:
            return False
        
        # Must have some volume dry-up or moderate liquidity
        if structure_health['volume_health']['score'] < 30:
            return False
        
        # Must have decent EMA context
        if structure_health['ema_health']['score'] < 30:
            return False
        
        return True
    
    def _generate_structure_rationale(
        self,
        structure_integrity: float,
        structure_health: Dict[str, Any],
        is_actionable: bool
    ) -> str:
        """Generate rationale for structure assessment"""
        components = []
        
        # Overall integrity
        if structure_integrity >= 70:
            components.append("Structure excellent")
        elif structure_integrity >= 50:
            components.append("Structure solid")
        else:
            components.append("Structure weak")
        
        # Add key factors
        all_factors = []
        for key in structure_health:
            all_factors.extend(structure_health[key]['factors'])
        
        # Add top 3 factors
        unique_factors = list(dict.fromkeys(all_factors))  # Preserve order, remove duplicates
        components.extend(unique_factors[:3])
        
        # Actionable status
        if is_actionable:
            components.append("Operationally actionable")
        else:
            components.append("Not actionable")
        
        return ". ".join(components) + "."
    
    def analyze_ma_context(self, metrics: StockMetrics) -> Dict[str, Any]:
        """
        Comprehensive MA contextual analysis.
        
        Evaluates:
        - EMA slope (rising, flat, rolling over)
        - EMA alignment (stacking order)
        - MA compression (EMAs converging)
        - MA expansion (EMAs diverging)
        - Slope acceleration (momentum in trend)
        
        Philosophy:
        - EMA50 rising aggressively ≠ EMA50 flat ≠ EMA50 rolling over
        - MA stacking indicates trend strength
        - Compression indicates setup tightening
        - Expansion indicates trend acceleration
        """
        ma_analysis = {}
        
        # 1. EMA slope analysis
        ema_slope = self._analyze_ema_slope(metrics)
        ma_analysis['ema_slope'] = ema_slope
        
        # 2. MA stacking analysis
        ma_stacking = self._analyze_ma_stacking(metrics)
        ma_analysis['ma_stacking'] = ma_stacking
        
        # 3. MA compression analysis
        ma_compression = self._analyze_ma_compression(metrics)
        ma_analysis['ma_compression'] = ma_compression
        
        # 4. MA expansion analysis
        ma_expansion = self._analyze_ma_expansion(metrics)
        ma_analysis['ma_expansion'] = ma_expansion
        
        # 5. Slope acceleration
        slope_acceleration = self._analyze_slope_acceleration(metrics)
        ma_analysis['slope_acceleration'] = slope_acceleration
        
        # Overall MA context score
        ma_context_score = (
            ema_slope['score'] * 0.30 +
            ma_stacking['score'] * 0.25 +
            ma_compression['score'] * 0.20 +
            ma_expansion['score'] * 0.15 +
            slope_acceleration['score'] * 0.10
        )
        
        # Generate MA narrative
        ma_narrative = self._generate_ma_narrative(
            ema_slope,
            ma_stacking,
            ma_compression,
            ma_expansion,
            slope_acceleration
        )
        
        return {
            'ma_context_score': min(100.0, max(0.0, ma_context_score)),
            'ema_slope': ema_slope,
            'ma_stacking': ma_stacking,
            'ma_compression': ma_compression,
            'ma_expansion': ma_expansion,
            'slope_acceleration': slope_acceleration,
            'narrative': ma_narrative
        }
    
    def _analyze_ema_slope(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze EMA slope characteristics"""
        score = 0.0
        factors = []
        
        # EMA50 slope (using distance to EMA50 as proxy for slope)
        if metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema50 >= 10:
                score += 40
                factors.append("EMA50 rising aggressively")
            elif metrics.distance_to_ema50 >= 5:
                score += 30
                factors.append("EMA50 rising steadily")
            elif metrics.distance_to_ema50 >= 0:
                score += 20
                factors.append("EMA50 rising moderately")
            elif metrics.distance_to_ema50 >= -5:
                score += 10
                factors.append("EMA50 flattening")
            else:
                score += 0
                factors.append("EMA50 rolling over")
        
        # EMA21 slope (using distance to EMA21 as proxy)
        if metrics.distance_to_ema21 is not None:
            if metrics.distance_to_ema21 >= 5:
                score += 30
                factors.append("EMA21 rising strongly")
            elif metrics.distance_to_ema21 >= 0:
                score += 20
                factors.append("EMA21 rising")
            elif metrics.distance_to_ema21 >= -3:
                score += 10
                factors.append("EMA21 flattening")
            else:
                score += 0
                factors.append("EMA21 declining")
        
        # EMA200 slope (using distance to EMA50 as proxy)
        if metrics.distance_to_ema50 is not None and metrics.ema200:
            # Estimate slope by comparing EMA50 to EMA200
            # This is a simplified proxy - in production would calculate actual slope
            if metrics.distance_to_ema50 > 0:
                score += 30
                factors.append("Above EMA200")
            elif metrics.distance_to_ema50 > -10:
                score += 15
                factors.append("Near EMA200")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_ma_stacking(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze MA stacking order (bullish vs bearish)"""
        score = 0.0
        factors = []
        
        # Ideal bullish stacking: price > EMA9 > EMA21 > EMA50 > EMA200
        if metrics.distance_to_ema9 is not None and metrics.distance_to_ema21 is not None:
            if metrics.distance_to_ema9 >= 0 and metrics.distance_to_ema21 >= 0:
                score += 40
                factors.append("Price above fast EMAs")
            elif metrics.distance_to_ema9 >= 0:
                score += 25
                factors.append("Price above EMA9")
        
        # EMA21 vs EMA50 stacking
        if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
            # This is a simplified check - actual stacking would compare EMA values directly
            if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
                if metrics.distance_to_ema21 > metrics.distance_to_ema50:
                    score += 30
                    factors.append("EMA21 above EMA50")
                else:
                    score += 20
                    factors.append("EMAs aligned")
            elif metrics.distance_to_ema21 >= 0:
                score += 15
                factors.append("EMA21 above EMA50")
        
        # EMA50 vs EMA200 stacking
        if metrics.distance_to_ema50 is not None:
            if metrics.distance_to_ema50 >= 10:
                score += 30
                factors.append("Well above EMA200")
            elif metrics.distance_to_ema50 >= 0:
                score += 20
                factors.append("Above EMA200")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_ma_compression(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze MA compression (EMAs converging)"""
        score = 0.0
        factors = []
        
        # ATR-normalized compression (distance to EMAs in ATR units)
        if metrics.distance_to_ema21_atr is not None and metrics.distance_to_ema50_atr is not None:
            # Calculate spread between EMA21 and EMA50 in ATR units
            ema_spread = abs(metrics.distance_to_ema21_atr - metrics.distance_to_ema50_atr)
            
            if ema_spread <= 0.5:
                score += 40
                factors.append("EMAs tightly compressed")
            elif ema_spread <= 1.0:
                score += 30
                factors.append("EMAs compressing")
            elif ema_spread <= 2.0:
                score += 15
                factors.append("EMAs moderately compressed")
            else:
                score += 5
                factors.append("EMAs diverging")
        
        # Weekly tightness as proxy for MA compression
        if metrics.weekly_tightness:
            if metrics.weekly_tightness >= 0.7:
                score += 30
                factors.append("Weekly structure tight")
            elif metrics.weekly_tightness >= 0.5:
                score += 20
                factors.append("Weekly structure compressing")
        
        # Volume contraction indicates setup compression
        if metrics.volume_contraction:
            if metrics.volume_contraction >= 0.5:
                score += 30
                factors.append("Volume drying up")
            elif metrics.volume_contraction >= 0.3:
                score += 15
                factors.append("Volume contracting")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_ma_expansion(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze MA expansion (EMAs diverging, trend acceleration)"""
        score = 0.0
        factors = []
        
        # ATR-normalized expansion
        if metrics.distance_to_ema21_atr is not None and metrics.distance_to_ema50_atr is not None:
            ema_spread = abs(metrics.distance_to_ema21_atr - metrics.distance_to_ema50_atr)
            
            if ema_spread >= 3.0:
                score += 40
                factors.append("EMAs expanding strongly")
            elif ema_spread >= 2.0:
                score += 30
                factors.append("EMAs expanding")
            elif ema_spread >= 1.0:
                score += 15
                factors.append("EMAs moderately expanding")
        
        # Price acceleration (using performance metrics)
        if metrics.perf_4w is not None and metrics.perf_13w is not None:
            if metrics.perf_4w > metrics.perf_13w:
                score += 30
                factors.append("Price accelerating")
            elif metrics.perf_4w > 0:
                score += 15
                factors.append("Price trending up")
        
        # RS acceleration
        if metrics.relative_strength_spy is not None and metrics.relative_strength_spy > 100:
            score += 30
            factors.append("RS accelerating")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_slope_acceleration(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze slope acceleration (momentum in trend)"""
        score = 0.0
        factors = []
        
        # Performance acceleration (4w vs 13w)
        if metrics.perf_4w is not None and metrics.perf_13w is not None:
            if metrics.perf_4w > metrics.perf_13w * 1.2:
                score += 40
                factors.append("Strong momentum acceleration")
            elif metrics.perf_4w > metrics.perf_13w:
                score += 30
                factors.append("Momentum accelerating")
            elif metrics.perf_4w > 0:
                score += 15
                factors.append("Positive momentum")
        
        # Weekly trend quality as proxy for slope health
        if metrics.weekly_trend_quality:
            if metrics.weekly_trend_quality >= 0.7:
                score += 30
                factors.append("Strong weekly momentum")
            elif metrics.weekly_trend_quality >= 0.5:
                score += 20
                factors.append("Solid weekly momentum")
        
        # ATR positioning (tight to EMA = better slope acceleration potential)
        if metrics.distance_to_ema21_atr is not None:
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 30
                factors.append("Near EMA21 (acceleration point)")
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 15
                factors.append("Near EMA21")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _generate_ma_narrative(
        self,
        ema_slope: Dict[str, Any],
        ma_stacking: Dict[str, Any],
        ma_compression: Dict[str, Any],
        ma_expansion: Dict[str, Any],
        slope_acceleration: Dict[str, Any]
    ) -> str:
        """Generate MA contextual narrative"""
        components = []
        
        # Add top factors from each analysis
        all_factors = []
        all_factors.extend(ema_slope['factors'][:2])
        all_factors.extend(ma_stacking['factors'][:2])
        all_factors.extend(ma_compression['factors'][:1])
        all_factors.extend(ma_expansion['factors'][:1])
        all_factors.extend(slope_acceleration['factors'][:1])
        
        # Remove duplicates while preserving order
        unique_factors = list(dict.fromkeys(all_factors))
        components.extend(unique_factors[:4])
        
        return ". ".join(components) + "."
    
    def analyze_pullback_character(self, metrics: StockMetrics) -> Dict[str, Any]:
        """
        Comprehensive pullback character analysis.
        
        Evaluates:
        - Orderly vs impulsive pullback
        - Volume dry-up pattern
        - Spread tightening
        - Close quality (where price closes relative to range)
        - Lower volatility retracement
        - Support reactions
        
        Philosophy:
        - Orderly pullbacks are more reliable than impulsive ones
        - Volume dry-up indicates supply exhaustion
        - Spread tightening indicates consolidation
        - Close quality shows conviction
        - Lower volatility retracements are constructive
        - Support reactions show demand
        """
        pullback_analysis = {}
        
        # 1. Orderliness analysis
        orderliness = self._analyze_pullback_orderliness(metrics)
        pullback_analysis['orderliness'] = orderliness
        
        # 2. Volume dry-up analysis
        volume_dryup = self._analyze_volume_dryup(metrics)
        pullback_analysis['volume_dryup'] = volume_dryup
        
        # 3. Spread tightening analysis
        spread_tightening = self._analyze_spread_tightening(metrics)
        pullback_analysis['spread_tightening'] = spread_tightening
        
        # 4. Close quality analysis
        close_quality = self._analyze_close_quality(metrics)
        pullback_analysis['close_quality'] = close_quality
        
        # 5. Volatility retracement analysis
        volatility_retracement = self._analyze_volatility_retracement(metrics)
        pullback_analysis['volatility_retracement'] = volatility_retracement
        
        # 6. Support reaction analysis
        support_reaction = self._analyze_support_reaction(metrics)
        pullback_analysis['support_reaction'] = support_reaction
        
        # Overall pullback character score
        pullback_character_score = (
            orderliness['score'] * 0.25 +
            volume_dryup['score'] * 0.20 +
            spread_tightening['score'] * 0.15 +
            close_quality['score'] * 0.15 +
            volatility_retracement['score'] * 0.15 +
            support_reaction['score'] * 0.10
        )
        
        # Generate pullback narrative
        pullback_narrative = self._generate_pullback_narrative(
            orderliness,
            volume_dryup,
            spread_tightening,
            close_quality,
            volatility_retracement,
            support_reaction
        )
        
        return {
            'pullback_character_score': min(100.0, max(0.0, pullback_character_score)),
            'orderliness': orderliness,
            'volume_dryup': volume_dryup,
            'spread_tightening': spread_tightening,
            'close_quality': close_quality,
            'volatility_retracement': volatility_retracement,
            'support_reaction': support_reaction,
            'narrative': pullback_narrative
        }
    
    def _analyze_pullback_orderliness(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze if pullback is orderly or impulsive"""
        score = 0.0
        factors = []
        
        # ATR-normalized positioning (orderly pullback = 0.5-2.0 ATRs below EMA21)
        if metrics.distance_to_ema21_atr is not None:
            if -2.0 <= metrics.distance_to_ema21_atr <= -0.5:
                score += 40
                factors.append("Orderly pullback depth")
            elif -3.0 <= metrics.distance_to_ema21_atr < -2.0:
                score += 25
                factors.append("Moderate pullback")
            elif -0.5 < metrics.distance_to_ema21_atr <= 0.5:
                score += 30
                factors.append("Shallow pullback")
            elif metrics.distance_to_ema21_atr < -3.0:
                score += 10
                factors.append("Impulsive pullback")
        
        # Pullback quality score as proxy for orderliness
        if metrics.pullback_quality_score:
            if metrics.pullback_quality_score >= 70:
                score += 30
                factors.append("High quality pullback")
            elif metrics.pullback_quality_score >= 50:
                score += 20
                factors.append("Moderate quality pullback")
        
        # Weekly tightness indicates orderly consolidation
        if metrics.weekly_tightness:
            if metrics.weekly_tightness >= 0.6:
                score += 30
                factors.append("Orderly weekly structure")
            elif metrics.weekly_tightness >= 0.4:
                score += 15
                factors.append("Moderate weekly structure")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_volume_dryup(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze volume dry-up pattern"""
        score = 0.0
        factors = []
        
        # Volume contraction
        if metrics.volume_contraction:
            if metrics.volume_contraction >= 0.7:
                score += 50
                factors.append("Strong volume dry-up")
            elif metrics.volume_contraction >= 0.5:
                score += 35
                factors.append("Moderate volume dry-up")
            elif metrics.volume_contraction >= 0.3:
                score += 20
                factors.append("Some volume dry-up")
            else:
                score += 5
                factors.append("No volume dry-up")
        
        # Relative volume
        if metrics.relative_volume is not None:
            if metrics.relative_volume <= 0.5:
                score += 30
                factors.append("Very low relative volume")
            elif metrics.relative_volume <= 0.8:
                score += 20
                factors.append("Low relative volume")
            elif metrics.relative_volume <= 1.2:
                score += 10
                factors.append("Normal relative volume")
        
        # Average volume comparison (10d vs 20d)
        if metrics.avg_volume_10d and metrics.avg_volume_20d:
            if metrics.avg_volume_10d < metrics.avg_volume_20d * 0.8:
                score += 20
                factors.append("Volume decreasing")
            elif metrics.avg_volume_10d < metrics.avg_volume_20d:
                score += 10
                factors.append("Volume slightly decreasing")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_spread_tightening(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze spread tightening (price range compression)"""
        score = 0.0
        factors = []
        
        # Weekly tightness
        if metrics.weekly_tightness:
            if metrics.weekly_tightness >= 0.7:
                score += 40
                factors.append("Tight weekly spreads")
            elif metrics.weekly_tightness >= 0.5:
                score += 25
                factors.append("Compressing spreads")
            elif metrics.weekly_tightness >= 0.3:
                score += 10
                factors.append("Moderate spreads")
        
        # ATR positioning (tight to EMA = spread tightening)
        if metrics.distance_to_ema21_atr is not None:
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 30
                factors.append("Price tight to EMA21")
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 20
                factors.append("Price near EMA21")
        
        # Weekly volatility contraction
        if metrics.weekly_volatility_contraction:
            if metrics.weekly_volatility_contraction >= 0.6:
                score += 30
                factors.append("Strong volatility contraction")
            elif metrics.weekly_volatility_contraction >= 0.4:
                score += 15
                factors.append("Moderate volatility contraction")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_close_quality(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze close quality (where price closes relative to range)"""
        score = 0.0
        factors = []
        
        # This is a simplified analysis - in production would analyze daily close patterns
        # Using ATR-normalized positioning as proxy for close quality
        if metrics.distance_to_ema21_atr is not None:
            # If near EMA21, likely closing near support/resistance
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 40
                factors.append("Closing near EMA21")
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 25
                factors.append("Closing near support")
        
        # Weekly trend quality indicates conviction
        if metrics.weekly_trend_quality:
            if metrics.weekly_trend_quality >= 0.7:
                score += 30
                factors.append("Strong conviction")
            elif metrics.weekly_trend_quality >= 0.5:
                score += 15
                factors.append("Moderate conviction")
        
        # Volume contraction + above EMAs = good close quality
        if metrics.volume_contraction and metrics.distance_to_ema21 is not None:
            if metrics.volume_contraction >= 0.5 and metrics.distance_to_ema21 >= 0:
                score += 30
                factors.append("Good close quality")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_volatility_retracement(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze if retracement is lower volatility"""
        score = 0.0
        factors = []
        
        # ATR % indicates current volatility
        if metrics.atr_percent:
            if metrics.atr_percent <= 5:
                score += 40
                factors.append("Low volatility retracement")
            elif metrics.atr_percent <= 10:
                score += 25
                factors.append("Moderate volatility retracement")
            elif metrics.atr_percent <= 15:
                score += 10
                factors.append("High volatility retracement")
        
        # ADR (Average Daily Range)
        if metrics.adr_percent:
            if metrics.adr_percent <= 5:
                score += 30
                factors.append("Low daily range")
            elif metrics.adr_percent <= 10:
                score += 15
                factors.append("Moderate daily range")
        
        # Weekly volatility contraction
        if metrics.weekly_volatility_contraction:
            if metrics.weekly_volatility_contraction >= 0.6:
                score += 30
                factors.append("Volatility contracting")
            elif metrics.weekly_volatility_contraction >= 0.4:
                score += 15
                factors.append("Volatility moderately contracting")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _analyze_support_reaction(self, metrics: StockMetrics) -> Dict[str, Any]:
        """Analyze support reactions"""
        score = 0.0
        factors = []
        
        # ATR-normalized positioning near EMA21 = support reaction
        if metrics.distance_to_ema21_atr is not None:
            if abs(metrics.distance_to_ema21_atr) <= 0.5:
                score += 40
                factors.append("Strong EMA21 support reaction")
            elif abs(metrics.distance_to_ema21_atr) <= 1.0:
                score += 25
                factors.append("Moderate EMA21 support reaction")
        
        # Distance to EMA50 (deeper support)
        if metrics.distance_to_ema50_atr is not None:
            if abs(metrics.distance_to_ema50_atr) <= 1.0:
                score += 30
                factors.append("Near EMA50 support")
            elif abs(metrics.distance_to_ema50_atr) <= 2.0:
                score += 15
                factors.append("Approaching EMA50 support")
        
        # Weekly tightness indicates support consolidation
        if metrics.weekly_tightness:
            if metrics.weekly_tightness >= 0.6:
                score += 30
                factors.append("Support consolidation")
        
        return {
            'score': min(100.0, score),
            'factors': factors
        }
    
    def _generate_pullback_narrative(
        self,
        orderliness: Dict[str, Any],
        volume_dryup: Dict[str, Any],
        spread_tightening: Dict[str, Any],
        close_quality: Dict[str, Any],
        volatility_retracement: Dict[str, Any],
        support_reaction: Dict[str, Any]
    ) -> str:
        """Generate pullback character narrative"""
        components = []
        
        # Add top factors from each analysis
        all_factors = []
        all_factors.extend(orderliness['factors'][:2])
        all_factors.extend(volume_dryup['factors'][:2])
        all_factors.extend(spread_tightening['factors'][:1])
        all_factors.extend(close_quality['factors'][:1])
        all_factors.extend(volatility_retracement['factors'][:1])
        all_factors.extend(support_reaction['factors'][:1])
        
        # Remove duplicates while preserving order
        unique_factors = list(dict.fromkeys(all_factors))
        components.extend(unique_factors[:4])
        
        return ". ".join(components) + "."
