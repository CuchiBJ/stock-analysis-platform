"""Legacy deterministic RS helper retained for historical calibration tests."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics


async def get_rs_pullback_baselines(
    db: AsyncSession,
    setups: list[StockMetrics],
    lookback_sessions: int = 5,
) -> dict[str, float]:
    """Return each candidate's SPY-relative-strength value N sessions ago.

    A single market-session baseline keeps the ranking deterministic and avoids
    per-symbol queries. Missing or stale history is handled neutrally by the
    scoring helper rather than excluding the candidate.
    """
    if not setups:
        return {}

    latest_date = max((setup.date for setup in setups if setup.date is not None), default=None)
    if latest_date is None:
        return {}

    dates = (await db.execute(
        select(StockMetrics.date)
        .where(StockMetrics.date <= latest_date)
        .distinct()
        .order_by(StockMetrics.date.desc())
        .limit(lookback_sessions + 1)
    )).scalars().all()
    if len(dates) <= lookback_sessions:
        return {}

    baseline_date = dates[lookback_sessions]
    symbols = [setup.symbol for setup in setups]
    rows = (await db.execute(
        select(StockMetrics.symbol, StockMetrics.relative_strength_spy).where(
            StockMetrics.symbol.in_(symbols),
            StockMetrics.date == baseline_date,
            StockMetrics.relative_strength_spy.isnot(None),
        )
    )).all()
    return {symbol: rs for symbol, rs in rows}


def calculate_relative_strength_pullback_score(
    current_rs: Optional[float],
    baseline_rs: Optional[float],
) -> tuple[float, dict]:
    """Score leadership during a pullback from RS level and five-session trend.

    Sixty percent rewards durable outperformance versus SPY; forty percent
    rewards an improving/stable RS line while the candidate is pulling back.
    Missing history is neutral so a data gap neither boosts nor excludes a name.
    """
    if current_rs is None or baseline_rs is None or baseline_rs == 0:
        return 50.0, {
            'current_rs': current_rs,
            'baseline_rs': baseline_rs,
            'rs_delta_pct': None,
            'level_score': None,
            'trend_score': None,
            'status': 'missing_history_neutral',
        }

    if current_rs >= 110:
        level_score = 100.0
    elif current_rs >= 105:
        level_score = 80.0
    elif current_rs >= 100:
        level_score = 60.0
    elif current_rs >= 95:
        level_score = 40.0
    else:
        level_score = 20.0

    rs_delta_pct = (current_rs - baseline_rs) / baseline_rs * 100.0
    if rs_delta_pct >= 2.0:
        trend_score = 100.0
        status = 'improving'
    elif rs_delta_pct >= 0.5:
        trend_score = 80.0
        status = 'improving'
    elif rs_delta_pct > -0.5:
        trend_score = 60.0
        status = 'stable'
    elif rs_delta_pct > -2.0:
        trend_score = 30.0
        status = 'deteriorating'
    else:
        trend_score = 0.0
        status = 'deteriorating'

    score = 0.60 * level_score + 0.40 * trend_score
    return score, {
        'current_rs': round(current_rs, 2),
        'baseline_rs': round(baseline_rs, 2),
        'rs_delta_pct': round(rs_delta_pct, 2),
        'level_score': level_score,
        'trend_score': trend_score,
        'status': status,
    }
