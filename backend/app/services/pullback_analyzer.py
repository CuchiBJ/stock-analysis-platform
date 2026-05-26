"""Pullback character analysis — orderliness, volume dry-up, spread, support."""

from typing import Any, Dict
from app.models.stock import StockMetrics


def score_pullback_character(metrics: StockMetrics) -> float:
    score = 0.0

    # Volume dry-up (40 pts)
    if metrics.volume_contraction is not None:
        if metrics.volume_contraction >= 0.7:
            score += 40
        elif metrics.volume_contraction >= 0.5:
            score += 25
        elif metrics.volume_contraction >= 0.3:
            score += 12

    # Proximity to EMA21 ATR-normalized (40 pts)
    if metrics.distance_to_ema21_atr is not None:
        d = metrics.distance_to_ema21_atr
        if -0.5 <= d <= 1.5:
            score += 40
        elif -1.0 <= d <= 2.5:
            score += 25
        elif d > -1.5:
            score += 10

    # Orderliness via weekly tightness (20 pts)
    if metrics.weekly_tightness is not None:
        if metrics.weekly_tightness >= 0.6:
            score += 20
        elif metrics.weekly_tightness >= 0.4:
            score += 12
        elif metrics.weekly_tightness >= 0.2:
            score += 6

    return min(100.0, score)


def analyze_pullback_character(metrics: StockMetrics) -> Dict[str, Any]:
    volume   = _analyze_volume_dryup(metrics)
    spread   = _analyze_price_spread(metrics)
    support  = _analyze_support_holding(metrics)

    character_score = (
        volume['score']  * 0.40 +
        spread['score']  * 0.35 +
        support['score'] * 0.25
    )

    return {
        'pullback_character_score': min(100.0, max(0.0, character_score)),
        'volume_dryup':             volume,
        'price_spread':             spread,
        'support_holding':          support,
        'narrative':                _generate_pullback_narrative(volume, spread, support),
    }


def _analyze_volume_dryup(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.volume_contraction is not None:
        if metrics.volume_contraction >= 0.7:
            score += 60; factors.append("Strong volume dry-up")
        elif metrics.volume_contraction >= 0.5:
            score += 40; factors.append("Moderate volume contraction")
        elif metrics.volume_contraction >= 0.3:
            score += 20; factors.append("Light volume contraction")
        else:
            factors.append("No meaningful volume contraction")

    if metrics.avg_volume_10d is not None:
        if metrics.avg_volume_10d >= 1_000_000:
            score += 40; factors.append("High institutional liquidity")
        elif metrics.avg_volume_10d >= 500_000:
            score += 25; factors.append("Adequate liquidity")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_price_spread(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.weekly_tightness is not None:
        if metrics.weekly_tightness >= 0.6:
            score += 50; factors.append("Tight weekly price spread")
        elif metrics.weekly_tightness >= 0.4:
            score += 30; factors.append("Moderate weekly spread")
        elif metrics.weekly_tightness >= 0.2:
            score += 10; factors.append("Wide weekly spread")

    if metrics.weekly_volatility_contraction is not None:
        if metrics.weekly_volatility_contraction >= 0.6:
            score += 50; factors.append("Volatility contracting")
        elif metrics.weekly_volatility_contraction >= 0.4:
            score += 30; factors.append("Volatility moderating")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_support_holding(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema21_atr is not None:
        d = metrics.distance_to_ema21_atr
        if -0.5 <= d <= 1.5:
            score += 60; factors.append("Holding near EMA21")
        elif -1.0 <= d <= 2.5:
            score += 35; factors.append("Within 2.5 ATRs of EMA21")
        elif d > -1.5:
            score += 15; factors.append("Extended below EMA21")

    if metrics.distance_to_ema50_atr is not None:
        if metrics.distance_to_ema50_atr > 0:
            score += 40; factors.append("Above EMA50")
        elif metrics.distance_to_ema50_atr >= -0.5:
            score += 20; factors.append("Testing EMA50")

    return {'score': min(100.0, score), 'factors': factors}


def _generate_pullback_narrative(
    volume: Dict[str, Any],
    spread: Dict[str, Any],
    support: Dict[str, Any],
) -> str:
    all_factors = volume['factors'] + spread['factors'] + support['factors']
    unique = list(dict.fromkeys(all_factors))[:3]
    return ". ".join(unique) + "." if unique else "Insufficient data for pullback characterization."
