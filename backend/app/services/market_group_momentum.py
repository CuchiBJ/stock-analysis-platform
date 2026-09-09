"""Two-horizon momentum for the canonical Sector Leadership market groups."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_sectors
from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.sector_service import SectorService


BENCHMARK = "SPY"
STRUCTURAL_SESSIONS = 20
MOMENTUM_SESSIONS = 5


def classify_market_group_signals(signals: list[dict]) -> list[dict]:
    """Attach rank and state without changing Sector Leadership's order."""
    leader_cutoff = max(1, math.ceil(len(signals) * 0.35))
    for rank, signal in enumerate(signals, start=1):
        accelerating = signal["acceleration_5d"] > 0
        structurally_strong = rank <= leader_cutoff and signal["relative_strength_4w"] > 0
        if structurally_strong and accelerating and signal["relative_strength_5d"] > 0:
            status = "hot"
        elif accelerating:
            status = "warming"
        else:
            status = "cooling"

        signal.update({
            "weekly_rank": rank,
            "status": status,
            "summary": (
                f"{'Fuerte' if signal['relative_strength_4w'] > 0 else 'Débil'} en cuatro semanas "
                f"(#{rank}, {signal['relative_strength_4w']:+.2f} pp vs SPY) y "
                f"{'acelerando' if accelerating else 'perdiendo velocidad'} en cinco días "
                f"({signal['acceleration_5d']:+.2f} pp)."
            ),
        })
    return signals


class MarketGroupMomentumService:
    """Enrich the existing Sector Leadership ranking with short-term momentum."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _benchmark_return(self, end_date: date, sessions: int) -> float | None:
        rows = (await self.db.execute(
            select(StockPrice.close)
            .where(StockPrice.symbol == BENCHMARK, StockPrice.date <= end_date)
            .order_by(StockPrice.date.desc())
            .limit(sessions + 1)
        )).scalars().all()
        if len(rows) < sessions + 1 or rows[sessions] in (None, 0):
            return None
        return (rows[0] / rows[sessions] - 1.0) * 100.0

    @cache_sectors
    async def calculate_leadership_momentum(self) -> dict:
        # This is the source of truth for the names, eligibility and structural
        # ordering rendered by Sector Leadership.
        leadership = await SectorService(self.db).calculate_sector_performance()

        dates = (await self.db.execute(
            select(StockMetrics.date).distinct().order_by(StockMetrics.date.desc()).limit(6)
        )).scalars().all()
        if len(dates) < 6 or not leadership:
            return self._empty(dates[0] if dates else None)

        date_now, date_previous_window = dates[0], dates[5]
        previous_rows = (await self.db.execute(
            select(Stock.market_group, StockMetrics.perf_1w)
            .join(Stock, Stock.symbol == StockMetrics.symbol)
            .where(
                StockMetrics.date == date_previous_window,
                Stock.market_group.isnot(None),
                StockMetrics.avg_volume_10d >= 800000,
                StockMetrics.current_price >= 5.0,
                StockMetrics.perf_1w.isnot(None),
            )
        )).all()

        previous_weekly: dict[str, list[float]] = defaultdict(list)
        for group, performance in previous_rows:
            if performance is not None and math.isfinite(performance):
                previous_weekly[group].append(performance)

        spy_5d = await self._benchmark_return(date_now, MOMENTUM_SESSIONS)
        spy_previous_5d = await self._benchmark_return(date_previous_window, MOMENTUM_SESSIONS)
        if spy_5d is None or spy_previous_5d is None:
            return self._empty(date_now)

        signals = []
        for group in leadership:
            prior_values = previous_weekly.get(group["name"], [])
            if not prior_values:
                continue
            relative_5d = group["performance_weekly"] - spy_5d
            prior_relative_5d = sum(prior_values) / len(prior_values) - spy_previous_5d
            acceleration = relative_5d - prior_relative_5d
            signals.append({
                "name": group["name"],
                "stock_count": group["stock_count"],
                "performance_4w": group["performance_monthly"],
                "relative_strength_4w": group["performance_vs_spy"],
                "relative_strength_5d": round(relative_5d, 2),
                "acceleration_5d": round(acceleration, 2),
            })

        ranked = classify_market_group_signals(signals)
        hot_now = sorted(
            [item for item in ranked if item["status"] in {"hot", "warming"}],
            key=lambda item: (
                item["status"] == "hot",
                item["acceleration_5d"],
                -item["weekly_rank"],
            ),
            reverse=True,
        )[:3]

        return {
            "benchmark": BENCHMARK,
            "taxonomy": "Sector Leadership",
            "universe": "market_groups",
            "as_of": date_now.isoformat(),
            "compared_to": date_previous_window.isoformat(),
            "structural_sessions": STRUCTURAL_SESSIONS,
            "momentum_sessions": MOMENTUM_SESSIONS,
            "hot_now": hot_now,
            "groups": ranked,
        }

    @staticmethod
    def _empty(as_of: date | None) -> dict:
        return {
            "benchmark": BENCHMARK,
            "taxonomy": "Sector Leadership",
            "universe": "market_groups",
            "as_of": as_of.isoformat() if as_of else None,
            "compared_to": None,
            "structural_sessions": STRUCTURAL_SESSIONS,
            "momentum_sessions": MOMENTUM_SESSIONS,
            "hot_now": [],
            "groups": [],
        }
