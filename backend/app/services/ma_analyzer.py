"""MA context analysis — slope, stacking, compression, expansion."""

from typing import Any, Dict
from app.models.stock import StockMetrics


def score_ma_context(metrics: StockMetrics) -> float:
    score = 0.0

    if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
            score += 40
        elif metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= -5:
            score += 25

    if metrics.distance_to_ema21_atr is not None:
        if abs(metrics.distance_to_ema21_atr) <= 1.0:
            score += 60
        elif abs(metrics.distance_to_ema21_atr) <= 2.0:
            score += 40
        elif abs(metrics.distance_to_ema21_atr) <= 3.0:
            score += 20

    return min(100.0, score)


def analyze_ma_context(metrics: StockMetrics) -> Dict[str, Any]:
    ema_slope         = _analyze_ema_slope(metrics)
    ma_stacking       = _analyze_ma_stacking(metrics)
    ma_compression    = _analyze_ma_compression(metrics)
    ma_expansion      = _analyze_ma_expansion(metrics)
    slope_accel       = _analyze_slope_acceleration(metrics)

    context_score = (
        ema_slope['score']      * 0.30 +
        ma_stacking['score']    * 0.25 +
        ma_compression['score'] * 0.20 +
        ma_expansion['score']   * 0.15 +
        slope_accel['score']    * 0.10
    )

    return {
        'ma_context_score':   min(100.0, max(0.0, context_score)),
        'ema_slope':          ema_slope,
        'ma_stacking':        ma_stacking,
        'ma_compression':     ma_compression,
        'ma_expansion':       ma_expansion,
        'slope_acceleration': slope_accel,
        'narrative':          _generate_ma_narrative(ema_slope, ma_stacking, ma_compression, ma_expansion, slope_accel),
    }


def _analyze_ema_slope(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema50 >= 10:
            score += 40; factors.append("EMA50 rising aggressively")
        elif metrics.distance_to_ema50 >= 5:
            score += 30; factors.append("EMA50 rising steadily")
        elif metrics.distance_to_ema50 >= 0:
            score += 20; factors.append("EMA50 rising moderately")
        elif metrics.distance_to_ema50 >= -5:
            score += 10; factors.append("EMA50 flattening")
        else:
            factors.append("EMA50 rolling over")

    if metrics.distance_to_ema21 is not None:
        if metrics.distance_to_ema21 >= 5:
            score += 30; factors.append("EMA21 rising strongly")
        elif metrics.distance_to_ema21 >= 0:
            score += 20; factors.append("EMA21 rising")
        elif metrics.distance_to_ema21 >= -3:
            score += 10; factors.append("EMA21 flattening")
        else:
            factors.append("EMA21 declining")

    if metrics.distance_to_ema50 is not None and metrics.ema200:
        if metrics.distance_to_ema50 > 0:
            score += 30; factors.append("Above EMA200")
        elif metrics.distance_to_ema50 > -10:
            score += 15; factors.append("Near EMA200")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_ma_stacking(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema9 is not None and metrics.distance_to_ema21 is not None:
        if metrics.distance_to_ema9 >= 0 and metrics.distance_to_ema21 >= 0:
            score += 40; factors.append("Price above fast EMAs")
        elif metrics.distance_to_ema9 >= 0:
            score += 25; factors.append("Price above EMA9")

    if metrics.distance_to_ema21 is not None and metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema21 >= 0 and metrics.distance_to_ema50 >= 0:
            if metrics.distance_to_ema21 > metrics.distance_to_ema50:
                score += 30; factors.append("EMA21 above EMA50")
            else:
                score += 20; factors.append("EMAs aligned")
        elif metrics.distance_to_ema21 >= 0:
            score += 15; factors.append("EMA21 above EMA50")

    if metrics.distance_to_ema50 is not None:
        if metrics.distance_to_ema50 >= 10:
            score += 30; factors.append("Well above EMA200")
        elif metrics.distance_to_ema50 >= 0:
            score += 20; factors.append("Above EMA200")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_ma_compression(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema21_atr is not None and metrics.distance_to_ema50_atr is not None:
        spread = abs(metrics.distance_to_ema21_atr - metrics.distance_to_ema50_atr)
        if spread <= 0.5:
            score += 40; factors.append("EMAs tightly compressed")
        elif spread <= 1.0:
            score += 30; factors.append("EMAs compressing")
        elif spread <= 2.0:
            score += 15; factors.append("EMAs moderately compressed")
        else:
            score += 5;  factors.append("EMAs diverging")

    if metrics.weekly_tightness:
        if metrics.weekly_tightness >= 0.7:
            score += 30; factors.append("Weekly structure tight")
        elif metrics.weekly_tightness >= 0.5:
            score += 20; factors.append("Weekly structure compressing")

    if metrics.volume_contraction:
        if metrics.volume_contraction >= 0.5:
            score += 30; factors.append("Volume drying up")
        elif metrics.volume_contraction >= 0.3:
            score += 15; factors.append("Volume contracting")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_ma_expansion(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.distance_to_ema21_atr is not None and metrics.distance_to_ema50_atr is not None:
        spread = abs(metrics.distance_to_ema21_atr - metrics.distance_to_ema50_atr)
        if spread >= 3.0:
            score += 40; factors.append("EMAs expanding strongly")
        elif spread >= 2.0:
            score += 30; factors.append("EMAs expanding")
        elif spread >= 1.0:
            score += 15; factors.append("EMAs moderately expanding")

    if metrics.perf_4w is not None and metrics.perf_13w is not None:
        if metrics.perf_4w > metrics.perf_13w:
            score += 30; factors.append("Price accelerating")
        elif metrics.perf_4w > 0:
            score += 15; factors.append("Price trending up")

    if metrics.relative_strength_spy is not None and metrics.relative_strength_spy > 100:
        score += 30; factors.append("RS accelerating")

    return {'score': min(100.0, score), 'factors': factors}


def _analyze_slope_acceleration(metrics: StockMetrics) -> Dict[str, Any]:
    score, factors = 0.0, []

    if metrics.perf_4w is not None and metrics.perf_13w is not None:
        if metrics.perf_4w > metrics.perf_13w * 1.2:
            score += 40; factors.append("Strong momentum acceleration")
        elif metrics.perf_4w > metrics.perf_13w:
            score += 30; factors.append("Momentum accelerating")
        elif metrics.perf_4w > 0:
            score += 15; factors.append("Positive momentum")

    if metrics.weekly_trend_quality:
        if metrics.weekly_trend_quality >= 0.7:
            score += 30; factors.append("Strong weekly momentum")
        elif metrics.weekly_trend_quality >= 0.5:
            score += 20; factors.append("Solid weekly momentum")

    if metrics.distance_to_ema21_atr is not None:
        if abs(metrics.distance_to_ema21_atr) <= 0.5:
            score += 30; factors.append("Near EMA21 (acceleration point)")
        elif abs(metrics.distance_to_ema21_atr) <= 1.0:
            score += 15; factors.append("Near EMA21")

    return {'score': min(100.0, score), 'factors': factors}


def _generate_ma_narrative(
    ema_slope: Dict,
    ma_stacking: Dict,
    ma_compression: Dict,
    ma_expansion: Dict,
    slope_accel: Dict,
) -> str:
    pool: list = []
    pool.extend(ema_slope['factors'][:2])
    pool.extend(ma_stacking['factors'][:2])
    pool.extend(ma_compression['factors'][:1])
    pool.extend(ma_expansion['factors'][:1])
    pool.extend(slope_accel['factors'][:1])
    unique = list(dict.fromkeys(pool))
    return ". ".join(unique[:4]) + "."
