"""Observation Priority Scorer — Pre-reclaim setup detection.

Answers: "how interesting is this stock to start monitoring?"
NOT a confirmation score. Rewards pre-reclaim quality:
structure intactness, RS persistence, pullback orderliness,
volatility contraction, and pullback depth.
"""

from app.models.stock import StockMetrics


def score_observation_priority(metrics: StockMetrics) -> float:
    """
    Score (0-100): how worth monitoring is this stock before it reclaims.

    Components:
    - Structure intactness (30%): weekly quality + EMA50 health
    - RS persistence     (25%): RS holding despite pullback
    - Pullback orderliness(20%): volume dry-up, no distribution
    - Volatility contraction(15%): compressing ATR + tightening
    - Pullback depth quality(10%): shallow preferred
    """
    score = 0.0

    # 1. Structure intactness (max 30)
    struct = 0.0
    if metrics.weekly_trend_quality is not None:
        struct += metrics.weekly_trend_quality * 15  # max 15
    if metrics.distance_to_ema50_atr is not None:
        d50 = metrics.distance_to_ema50_atr
        if d50 > 0.5:    struct += 15   # EMA50 well above — healthy uptrend
        elif d50 > 0:    struct += 10
        elif d50 > -0.5: struct += 5    # Testing EMA50, still acceptable
    score += struct  # max 30

    # 2. RS persistence (max 25)
    rs_score = 0.0
    if metrics.relative_strength_spy is not None:
        rs = metrics.relative_strength_spy
        if rs >= 110:   rs_score = 25
        elif rs >= 105: rs_score = 20
        elif rs >= 100: rs_score = 15
        elif rs >= 97:  rs_score = 10
        elif rs >= 95:  rs_score = 5
        # RS < 95 = 0 (RS holding during pullback is the key institutional signal)
    else:
        rs_score = 10  # No RS data yet → neutral, don't penalize
    score += rs_score  # max 25

    # 3. Pullback orderliness (max 20)
    orderly = 0.0
    if metrics.volume_contraction is not None and metrics.volume_contraction > 0:
        orderly += min(12, metrics.volume_contraction * 12)  # max 12
    if metrics.relative_volume is not None:
        rvol = metrics.relative_volume
        if rvol < 0.6:   orderly += 8   # strong dry-up
        elif rvol < 0.8: orderly += 5
        elif rvol < 1.0: orderly += 2
        # rvol > 1.2 during pullback = distribution = 0
    score += min(20, orderly)  # max 20

    # 4. Volatility contraction (max 15)
    vol_c = 0.0
    if metrics.weekly_volatility_contraction is not None:
        vol_c += metrics.weekly_volatility_contraction * 10  # max 10
    if metrics.weekly_tightness is not None:
        vol_c += metrics.weekly_tightness * 5  # max 5
    score += min(15, vol_c)  # max 15

    # 5. Pullback depth quality (max 10)
    # Sweet spot: 0.3–1.5 ATR below EMA21
    depth = 0.0
    if metrics.distance_to_ema21_atr is not None:
        d = metrics.distance_to_ema21_atr
        if -1.5 <= d < -0.3:   depth = 10  # sweet spot
        elif -0.3 <= d < 0:    depth = 6   # very close, reclaim may be imminent
        elif -3.0 <= d < -1.5: depth = 5   # deeper but acceptable
        elif d < -3.0:         depth = 2   # too deep, higher risk
    score += depth  # max 10

    return min(100.0, max(0.0, score))


def score_breakout_quality(metrics: StockMetrics) -> float:
    """
    Score (0-100): qué tan maduro está un setup de breakout (coiling).

    A diferencia de `score_observation_priority` (orientado a pullbacks),
    este premia el coiling cerca de máximos con volumen seco — la fase
    anticipatoria del punto de compra de Minervini.

    Buckets calibrados a la distribución real del universo institucional
    (igual filosofía que `pullback_quality_score`: el máximo es alcanzable y
    la escala es comparable, para que un breakout fuerte pueda rankear por
    encima de un pullback). Los ~45 pts que en pullbacks da la proximidad a
    EMA9/21 acá se reasignan a las dimensiones propias del breakout.

    Components:
    - Proximidad al pivote 52w (30): cuanto más cerca del máximo, mejor
    - Tightness semanal        (25): base apretada (techo real ~0.48)
    - Dry-up de volumen        (20): volume_contraction + rvol bajo
    - Calidad de tendencia      (15): higher highs/lows semanales
    - Madurez de la base        (10): semanas en base
    """
    score = 0.0

    # 1. Proximidad al pivote / máximo 52w (max 30)
    if metrics.distance_to_high_52w_atr is not None:
        d = metrics.distance_to_high_52w_atr
        if d >= -0.3:    score += 30   # pegado al pivote
        elif d >= -0.6:  score += 25
        elif d >= -1.0:  score += 20
        elif d >= -1.5:  score += 12

    # 2. Tightness semanal (max 25) — buckets por percentil (techo real ~0.48)
    if metrics.weekly_tightness is not None:
        t = metrics.weekly_tightness
        if t >= 0.45:   score += 25
        elif t >= 0.40: score += 22
        elif t >= 0.37: score += 18
        elif t >= 0.34: score += 12
        elif t >= 0.30: score += 6

    # 3. Dry-up de volumen (max 20)
    dry = 0.0
    if metrics.volume_contraction is not None:
        vc = metrics.volume_contraction
        if vc >= 0.60:   dry += 12
        elif vc >= 0.40: dry += 9
        elif vc >= 0.20: dry += 5
        elif vc >= 0.05: dry += 2
    if metrics.relative_volume is not None:
        rvol = metrics.relative_volume
        if rvol < 0.4:   dry += 8
        elif rvol < 0.6: dry += 6
        elif rvol < 0.8: dry += 3
    score += min(20, dry)

    # 4. Calidad de tendencia semanal (max 15)
    if metrics.weekly_trend_quality is not None:
        wtq = metrics.weekly_trend_quality
        if wtq >= 0.70:   score += 15
        elif wtq >= 0.60: score += 11
        elif wtq >= 0.50: score += 7
        else:             score += 3

    # 5. Madurez de la base (max 10)
    if metrics.weeks_in_base is not None:
        w = metrics.weeks_in_base
        if w >= 10:  score += 10
        elif w >= 7: score += 7
        elif w >= 5: score += 5
        elif w >= 4: score += 3

    return min(100.0, max(0.0, score))


def is_pre_reclaim_candidate(metrics: StockMetrics) -> bool:
    """Quick boolean: stock just lost EMA9/EMA21 (in the trigger zone).

    Pre-reclaim = institutional setup that just CROSSED BELOW EMA9 or EMA21,
    or is very close to losing it. Not for stocks deep in pullback.

    Criteria:
    - In the trigger zone: -1.0 to 0 ATR below EMA9 or EMA21
    - EMA50 still above price NOT required here (the SQL filter already
      enforces price > EMA50 via _INSTITUTIONAL_SETUP)
    """
    ema9 = metrics.distance_to_ema9_atr
    ema21 = metrics.distance_to_ema21_atr

    just_lost_ema9  = ema9  is not None and -1.0 <= ema9  < 0
    just_lost_ema21 = ema21 is not None and -1.0 <= ema21 < 0

    return just_lost_ema9 or just_lost_ema21
