"""Shared quality filters for institutional universe calculations."""
from app.models.stock import StockMetrics

# Minimum quality thresholds applied to all breadth/leadership calculations.
# Prevents illiquid/penny stocks from contaminating regime and health signals.
QUALITY_FILTERS = [
    StockMetrics.avg_volume_10d >= 500_000,
    StockMetrics.current_price >= 5.0,
    StockMetrics.adr_percent >= 2.0,
    StockMetrics.adr_percent.isnot(None),
]
