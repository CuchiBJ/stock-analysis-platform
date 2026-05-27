"""Shared quality filters for institutional universe calculations.

These are the LIQUIDITY prerequisites for any setup in the platform —
applied to /actionable, /live, all queue lenses, batch_transition_scanner,
breadth/leadership engines, sector aggregations.

Thresholds match `_INSTITUTIONAL_SETUP` in transitions.py so every list
operates on the same playable universe.
"""
from app.models.stock import StockMetrics

QUALITY_FILTERS = [
    StockMetrics.avg_volume_10d >= 800_000,   # institutional liquidity
    StockMetrics.current_price >= 5.0,         # excludes penny stocks
    StockMetrics.adr_percent >= 4.0,           # operational volatility minimum
    StockMetrics.adr_percent.isnot(None),
]
