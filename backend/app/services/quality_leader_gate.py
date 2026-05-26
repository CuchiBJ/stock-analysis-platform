"""Minervini SEPA quality gate — shared helper.

Single source of truth for the 8 institutional leader criteria, used by
both transition_engine (for transition classification) and
setup_queue_service (for U&R and Building Bases queue filtering).
"""
from app.models.stock import StockMetrics


def is_quality_leader(m: StockMetrics) -> bool:
    """Eight Minervini SEPA criteria — all must pass.

    1. perf_1y > 30%
    2. price > EMA200
    3. price > EMA50 (via distance_to_ema50_atr > 0)
    4. SMA50 > SMA150
    5. SMA150 > SMA200 * 1.05
    6. 52W range >= 60% (skipped if high_52w is NULL, e.g. FAST cycles)
    7. price_above_low_pct >= 70%
    8. ADR >= 3%
    """
    if not all([
        m.perf_1y is not None, m.ema200 is not None,
        m.current_price is not None, m.sma50 is not None,
        m.sma150 is not None, m.sma200 is not None,
        m.low_52w is not None, m.adr_percent is not None,
    ]):
        return False
    if m.low_52w == 0:
        return False
    price_above_low_pct = (m.current_price - m.low_52w) / m.low_52w
    if m.high_52w is not None:
        range_52w_pct = (m.high_52w - m.low_52w) / m.low_52w
        if range_52w_pct < 0.60:
            return False
    return (
        m.perf_1y > 30.0 and
        m.current_price > m.ema200 and
        (m.distance_to_ema50_atr or 0.0) > 0 and
        m.sma50 > m.sma150 and
        m.sma150 > m.sma200 * 1.05 and
        price_above_low_pct >= 0.70 and
        m.adr_percent >= 3.0
    )


def evaluate_minervini_criteria(m: StockMetrics) -> dict:
    """Per-criterion breakdown for emerging leaders view.

    Returns a dict with each of the 8 criteria as {passes, value?, threshold?, detail?}.
    Used by the emerging leaders endpoint to show WHY each candidate doesn't fully qualify.
    """
    result = {}

    if m.perf_1y is not None:
        result['perf_1y_gt_30'] = {
            'passes': m.perf_1y > 30.0,
            'value': m.perf_1y,
            'threshold': 30.0,
        }
    else:
        result['perf_1y_gt_30'] = {'passes': False, 'detail': 'perf_1y is null'}

    if m.current_price is not None and m.ema200 is not None:
        result['price_above_ema200'] = {
            'passes': m.current_price > m.ema200,
            'value': m.current_price,
            'threshold': m.ema200,
        }
    else:
        result['price_above_ema200'] = {'passes': False, 'detail': 'missing price or ema200'}

    if m.distance_to_ema50_atr is not None:
        result['price_above_ema50'] = {
            'passes': m.distance_to_ema50_atr > 0,
            'value': m.distance_to_ema50_atr,
            'threshold': 0.0,
        }
    else:
        result['price_above_ema50'] = {'passes': False, 'detail': 'distance_to_ema50_atr is null'}

    if m.sma50 is not None and m.sma150 is not None:
        result['sma50_gt_sma150'] = {
            'passes': m.sma50 > m.sma150,
            'value': m.sma50,
            'threshold': m.sma150,
        }
    else:
        result['sma50_gt_sma150'] = {'passes': False, 'detail': 'missing sma50 or sma150'}

    if m.sma150 is not None and m.sma200 is not None:
        threshold = m.sma200 * 1.05
        result['sma150_gt_sma200_x_105'] = {
            'passes': m.sma150 > threshold,
            'value': m.sma150,
            'threshold': threshold,
        }
    else:
        result['sma150_gt_sma200_x_105'] = {'passes': False, 'detail': 'missing sma150 or sma200'}

    if m.high_52w is not None and m.low_52w is not None and m.low_52w > 0:
        range_pct = (m.high_52w - m.low_52w) / m.low_52w
        result['range_52w_gte_60pct'] = {
            'passes': range_pct >= 0.60,
            'value': range_pct * 100,
            'threshold': 60.0,
        }
    else:
        result['range_52w_gte_60pct'] = {'passes': False, 'detail': 'missing high_52w or low_52w'}

    if m.current_price is not None and m.low_52w is not None and m.low_52w > 0:
        above_low_pct = (m.current_price - m.low_52w) / m.low_52w
        result['price_above_low_gte_70pct'] = {
            'passes': above_low_pct >= 0.70,
            'value': above_low_pct * 100,
            'threshold': 70.0,
        }
    else:
        result['price_above_low_gte_70pct'] = {'passes': False, 'detail': 'missing current_price or low_52w'}

    if m.adr_percent is not None:
        result['adr_gte_3pct'] = {
            'passes': m.adr_percent >= 3.0,
            'value': m.adr_percent,
            'threshold': 3.0,
        }
    else:
        result['adr_gte_3pct'] = {'passes': False, 'detail': 'adr_percent is null'}

    return result
