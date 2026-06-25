"""API endpoint for Market Context Engine — Phase 1."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import StockPrice, StockMetrics
from app.services.benchmarks import compute_index_trend
from app.services.market_context_engine import MarketContextEngine

router = APIRouter(prefix="/market-context", tags=["market-context"])


async def _build_index_block(db: AsyncSession, symbol: str = "SPY"):
    """Live-ish SPY tile: freshest intraday price from stock_prices, daily
    variation vs the previous day's close, trend from the stock_metrics MAs.

    Returns None when there is no price row for the symbol.
    """
    price_rows = (await db.execute(
        select(StockPrice.date, StockPrice.close)
        .where(StockPrice.symbol == symbol)
        .order_by(desc(StockPrice.date))
        .limit(2)
    )).all()
    if not price_rows:
        return None

    price = price_rows[0].close
    prev_close = price_rows[1].close if len(price_rows) > 1 else None
    change_pct = (
        (price - prev_close) / prev_close * 100.0
        if prev_close not in (None, 0)
        else None
    )

    m = (await db.execute(
        select(
            StockMetrics.ema50, StockMetrics.ema200,
            StockMetrics.sma150, StockMetrics.sma200,
        )
        .where(StockMetrics.symbol == symbol)
        .order_by(desc(StockMetrics.date))
        .limit(1)
    )).first()
    ema50 = m.ema50 if m else None
    ema200 = m.ema200 if m else None
    sma150 = m.sma150 if m else None
    sma200 = m.sma200 if m else None

    return {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "trend": compute_index_trend(price, ema50, ema200, sma150, sma200),
        "above_ema50": (ema50 is not None and price > ema50),
        "above_ema200": (ema200 is not None and price > ema200),
    }


@router.get("/current")
async def get_current_market_context(db: AsyncSession = Depends(get_db)):
    """Get current multi-dimensional market context (cached ~5 min).

    Returns participation and leadership behavior engines for the latest
    stock_metrics date. The five remaining engines are listed in
    `engines_pending`.
    """
    engine = MarketContextEngine(db)
    ctx = await engine.analyze()

    if ctx is None:
        raise HTTPException(status_code=404, detail="No market data available — stock_metrics is empty")

    return {
        "as_of": ctx.as_of.isoformat(),
        "universe_size": ctx.universe_size,
        "participation": {
            "descriptor":           ctx.participation.descriptor,
            "delta_5d":             ctx.participation.delta_5d,
            "delta_sample_size_20d": ctx.participation.delta_sample_size_20d,
            "metrics":              ctx.participation.metrics,
            "history":              ctx.participation_history,
        },
        "leadership": {
            "descriptor": ctx.leadership.descriptor,
            "delta_5d":   ctx.leadership.delta_5d,
            "metrics":    ctx.leadership.metrics,
            "history":    ctx.leadership_history,
        },
        "engines_pending": ctx.engines_pending,
        "index": await _build_index_block(db),
    }
