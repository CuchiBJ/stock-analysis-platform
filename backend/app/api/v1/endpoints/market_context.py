"""API endpoint for Market Context Engine — Phase 1."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.services.market_context_engine import MarketContextEngine

router = APIRouter(prefix="/market-context", tags=["market-context"])


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
        },
        "leadership": {
            "descriptor": ctx.leadership.descriptor,
            "delta_5d":   ctx.leadership.delta_5d,
            "metrics":    ctx.leadership.metrics,
        },
        "engines_pending": ctx.engines_pending,
    }
