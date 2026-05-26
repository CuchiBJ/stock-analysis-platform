"""Structure quality scoring — weekly structure, EMA health, volume behavior."""

from typing import Any, Dict
from app.models.stock import StockMetrics


def score_structure_quality(metrics: StockMetrics) -> float:
    score = 0.0

    if metrics.weekly_trend_quality:
        score += metrics.weekly_trend_quality * 40

    if metrics.weekly_tightness:
        score += metrics.weekly_tightness * 30

    if metrics.setup_quality:
        score += {'excellent': 20, 'good': 15, 'fair': 10}.get(metrics.setup_quality, 0)

    if metrics.weeks_in_base:
        if 4 <= metrics.weeks_in_base <= 12:
            score += 10
        elif 2 <= metrics.weeks_in_base < 4:
            score += 5
        elif metrics.weeks_in_base > 12:
            score += 7

    return min(100.0, score)


def evaluate_structure(metrics: StockMetrics) -> Dict[str, Any]:
    weekly   = _evaluate_weekly_structure(metrics)
    volume   = _evaluate_volume_behavior(metrics)
    rs       = _evaluate_rs_holding(metrics)
    ema      = _evaluate_ema_health(metrics)
    vol_hlth = _evaluate_volatility_health(metrics)

    health = {
        'weekly_integrity': weekly,
        'volume_health':    volume,
        'rs_health':        rs,
        'ema_health':       ema,
        'volatility_health': vol_hlth,
    }

    integrity = (
        weekly['score']   * 0.30 +
        volume['score']   * 0.20 +
        rs['score']       * 0.20 +
        ema['score']      * 0.15 +
        vol_hlth['score'] * 0.15
    )

    is_actionable = _is_structure_actionable(integrity, health)

    return {
        'structure_integrity': min(100.0, max(0.0, integrity)),
        'structure_health':    health,
        'is_actionable':       is_actionable,
        'rationale':           _generate_structure_rationale(integrity, health, is_actionable),
    }


def _evaluate_weekly_structure(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.weekly_trend_quality:
        if metrics.weekly_trend_quality >= 0.7:
            score += 40; factors.append("Strong weekly trend")
        elif metrics.weekly_trend_quality >= 0.5:
            score += 25; factors.append("Solid weekly trend")
        elif metrics.weekly_trend_quality >= 0.3:
            score += 10; factors.append("Weak weekly trend")

    if metrics.weekly_tightness:
        if metrics.weekly_tightness >= 0.6:
            score += 30; factors.append("Tight weekly structure")
        elif metrics.weekly_tightness >= 0.4:
            score += 15; factors.append("Moderate tightness")

    if metrics.weeks_in_base:
        if 4 <= metrics.weeks_in_base <= 12:
            score += 30; factors.append("Optimal base length")
        elif 2 <= metrics.weeks_in_base < 4:
            score += 15; factors.append("Early base")
        elif metrics.weeks_in_base > 12:
            score += 20; factors.append("Extended base")

    return {'score': score, 'factors': factors}


def _evaluate_volume_behavior(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.volume_contraction:
        if metrics.volume_contraction >= 0.7:
            score += 50; factors.append("Strong volume dry-up")
        elif metrics.volume_contraction >= 0.5:
            score += 35; factors.append("Moderate volume dry-up")
        elif metrics.volume_contraction >= 0.3:
            score += 15; factors.append("Some volume contraction")

    if metrics.avg_volume_10d:
        if metrics.avg_volume_10d >= 1_000_000:
            score += 50; factors.append("High liquidity")
        elif metrics.avg_volume_10d >= 500_000:
            score += 30; factors.append("Good liquidity")
        elif metrics.avg_volume_10d >= 200_000:
            score += 10; factors.append("Adequate liquidity")

    return {'score': score, 'factors': factors}


def _evaluate_rs_holding(metrics: StockMetrics) -> Dict[str, Any]:
    if not metrics.relative_strength_spy and not metrics.relative_strength_qqq:
        return {'score': 50.0, 'factors': ["RS data unavailable"]}

    score, factors = 0.0, []

    if metrics.relative_strength_spy:
        if metrics.relative_strength_spy >= 105:
            score += 50; factors.append("Strong RS vs SPY")
        elif metrics.relative_strength_spy >= 100:
            score += 35; factors.append("Solid RS vs SPY")
        elif metrics.relative_strength_spy >= 95:
            score += 15; factors.append("Weak RS vs SPY")

    if metrics.relative_strength_qqq:
        if metrics.relative_strength_qqq >= 105:
            score += 50; factors.append("Strong RS vs QQQ")
        elif metrics.relative_strength_qqq >= 100:
            score += 35; factors.append("Solid RS vs QQQ")
        elif metrics.relative_strength_qqq >= 95:
            score += 15; factors.append("Weak RS vs QQQ")

    return {'score': min(100.0, score), 'factors': factors}


def _evaluate_ema_health(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
            score += 40; factors.append("EMA alignment bullish")
        elif metrics.distance_to_ema21 >= 0:
            score += 25; factors.append("Above EMA21")

    if metrics.distance_to_ema21_atr is not None:
        if abs(metrics.distance_to_ema21_atr) <= 1.0:
            score += 30; factors.append("Near EMA21 (ATR-normalized)")
        elif abs(metrics.distance_to_ema21_atr) <= 2.0:
            score += 15; factors.append("Within 2 ATRs of EMA21")

    if metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema50 >= 0:
            score += 30; factors.append("Above EMA50")
        elif metrics.distance_to_ema50 >= -5:
            score += 15; factors.append("Near EMA50")

    return {'score': score, 'factors': factors}


def _evaluate_volatility_health(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.weekly_volatility_contraction:
        if metrics.weekly_volatility_contraction >= 0.6:
            score += 40; factors.append("Strong volatility contraction")
        elif metrics.weekly_volatility_contraction >= 0.4:
            score += 25; factors.append("Moderate volatility contraction")

    if metrics.distance_to_ema21_atr is not None:
        if abs(metrics.distance_to_ema21_atr) <= 0.5:
            score += 30; factors.append("Tight to EMA21")
        elif abs(metrics.distance_to_ema21_atr) <= 1.0:
            score += 20; factors.append("Near EMA21")

    if metrics.adr_percent:
        if metrics.adr_percent <= 5:
            score += 30; factors.append("Low volatility")
        elif metrics.adr_percent <= 10:
            score += 15; factors.append("Moderate volatility")

    return {'score': score, 'factors': factors}


def _is_structure_actionable(integrity: float, health: Dict[str, Any]) -> bool:
    return not (
        integrity < 50
        or health['weekly_integrity']['score'] < 40
        or health['volume_health']['score'] < 30
        or health['ema_health']['score'] < 30
    )


def _generate_structure_rationale(
    integrity: float,
    health: Dict[str, Any],
    is_actionable: bool,
) -> str:
    label = "Structure excellent" if integrity >= 70 else ("Structure solid" if integrity >= 50 else "Structure weak")
    all_factors: list = []
    for key in health:
        all_factors.extend(health[key]['factors'])
    unique = list(dict.fromkeys(all_factors))
    parts = [label] + unique[:3] + (["Operationally actionable"] if is_actionable else ["Not actionable"])
    return ". ".join(parts) + "."
