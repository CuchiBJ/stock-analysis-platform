"""Shared quality filters for institutional universe calculations.

These are the prerequisites for any setup in the platform — applied to
/actionable, /live, all queue lenses, batch_transition_scanner,
breadth/leadership engines, sector aggregations.

Universe definition (institutional swing momentum):
  - Market cap ≥ $600M (large/mid cap only — no micro/small caps)
  - Volume ≥ 800k shares/day (institutional liquidity)
  - Price ≥ $5 (excludes penny stocks)
  - ADR ≥ 4% (operational volatility minimum)

The market_cap filter implicitly excludes stocks with NULL market_cap.
A backfill from yfinance keeps the field populated for active universe
candidates.
"""
from sqlalchemy import select
from app.models.stock import Stock, StockMetrics

# Subquery: symbols whose stocks.market_cap ≥ 600M.
# Used via .in_() in QUALITY_FILTERS to compose cleanly with StockMetrics
# expressions without forcing every caller to add a JOIN.
_LARGE_CAP_SYMBOLS = (
    select(Stock.symbol).where(Stock.market_cap >= 600_000_000)
)

QUALITY_FILTERS = [
    StockMetrics.symbol.in_(_LARGE_CAP_SYMBOLS),  # mid/large cap only
    StockMetrics.avg_volume_10d >= 800_000,        # institutional liquidity
    StockMetrics.current_price >= 5.0,              # excludes penny stocks
    StockMetrics.adr_percent >= 4.0,                # operational volatility minimum
    StockMetrics.adr_percent.isnot(None),
]
