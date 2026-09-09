"""Relative momentum for the standard US sector SPDR ETFs.

The signal intentionally keeps two horizons separate:

* 20 sessions: structural leadership versus SPY (the primary ranking)
* 5 sessions: current relative momentum and its change versus the prior 5 sessions

This is an ETF-level market-context signal.  It does not replace the more granular
``market_group`` aggregation used to rank individual-stock groups.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_sectors
from app.models.stock import StockPrice


SECTOR_ETFS: dict[str, str] = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}
BENCHMARK = "SPY"
STRUCTURAL_SESSIONS = 20
ACCELERATION_SESSIONS = 5


def _return_pct(end: float, start: float) -> float:
    if start == 0:
        raise ValueError("start price cannot be zero")
    return (end / start - 1.0) * 100.0


def calculate_etf_signal(
    symbol: str,
    name: str,
    etf_prices: dict[date, float],
    benchmark_prices: dict[date, float],
) -> dict | None:
    """Calculate a sector signal on dates shared with the benchmark.

    Eleven shared closes are enough for the two adjacent 5-session windows, while
    21 shared closes are required for the structural 4-week reading.
    """
    common_dates = sorted(set(etf_prices) & set(benchmark_prices))
    if len(common_dates) < STRUCTURAL_SESSIONS + 1:
        return None

    latest = common_dates[-1]
    d_5 = common_dates[-(ACCELERATION_SESSIONS + 1)]
    d_10 = common_dates[-(ACCELERATION_SESSIONS * 2 + 1)]
    d_20 = common_dates[-(STRUCTURAL_SESSIONS + 1)]

    etf_4w = _return_pct(etf_prices[latest], etf_prices[d_20])
    spy_4w = _return_pct(benchmark_prices[latest], benchmark_prices[d_20])
    relative_4w = etf_4w - spy_4w

    recent_etf = _return_pct(etf_prices[latest], etf_prices[d_5])
    recent_spy = _return_pct(benchmark_prices[latest], benchmark_prices[d_5])
    relative_5d = recent_etf - recent_spy

    prior_etf = _return_pct(etf_prices[d_5], etf_prices[d_10])
    prior_spy = _return_pct(benchmark_prices[d_5], benchmark_prices[d_10])
    prior_relative_5d = prior_etf - prior_spy
    acceleration_5d = relative_5d - prior_relative_5d

    values = (etf_4w, relative_4w, relative_5d, acceleration_5d)
    if not all(math.isfinite(value) for value in values):
        return None

    return {
        "symbol": symbol,
        "name": name,
        "as_of": latest.isoformat(),
        "performance_4w": round(etf_4w, 2),
        "relative_strength_4w": round(relative_4w, 2),
        "relative_strength_5d": round(relative_5d, 2),
        "acceleration_5d": round(acceleration_5d, 2),
    }


def classify_signals(signals: list[dict]) -> list[dict]:
    """Rank structural leadership and attach a compact, transition-first state."""
    ranked = sorted(signals, key=lambda item: item["relative_strength_4w"], reverse=True)
    leader_cutoff = max(1, math.ceil(len(ranked) * 0.35))

    for rank, signal in enumerate(ranked, start=1):
        accelerating = signal["acceleration_5d"] > 0
        structurally_strong = rank <= leader_cutoff and signal["relative_strength_4w"] > 0
        if structurally_strong and accelerating and signal["relative_strength_5d"] > 0:
            status = "hot"
        elif accelerating:
            status = "warming"
        else:
            status = "cooling"

        direction = "accelerating" if accelerating else "decelerating"
        structure = "strong" if signal["relative_strength_4w"] > 0 else "weak"
        signal.update({
            "weekly_rank": rank,
            "status": status,
            "summary": (
                f"{structure.capitalize()} over four weeks (#{rank}, "
                f"{signal['relative_strength_4w']:+.2f} pp vs SPY) and {direction} "
                f"over five days ({signal['acceleration_5d']:+.2f} pp)."
            ),
        })
    return ranked


class SectorEtfMomentumService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @cache_sectors
    async def calculate_etf_momentum(self) -> dict:
        symbols = [BENCHMARK, *SECTOR_ETFS]
        rows = (await self.db.execute(
            select(StockPrice.symbol, StockPrice.date, StockPrice.close)
            .where(StockPrice.symbol.in_(symbols))
            .order_by(StockPrice.date.desc())
            .limit(len(symbols) * 40)
        )).all()

        prices: dict[str, dict[date, float]] = defaultdict(dict)
        for row in rows:
            prices[row.symbol][row.date] = row.close

        signals = []
        for symbol, name in SECTOR_ETFS.items():
            signal = calculate_etf_signal(symbol, name, prices[symbol], prices[BENCHMARK])
            if signal:
                signals.append(signal)

        ranked = classify_signals(signals)
        hot_now = sorted(
            [item for item in ranked if item["status"] in {"hot", "warming"}],
            key=lambda item: (
                item["status"] == "hot",
                item["acceleration_5d"],
                -item["weekly_rank"],
            ),
            reverse=True,
        )[:3]
        available = {item["symbol"] for item in ranked}

        return {
            "role": "secondary_confirmation",
            "benchmark": BENCHMARK,
            "as_of": max((item["as_of"] for item in ranked), default=None),
            "structural_sessions": STRUCTURAL_SESSIONS,
            "acceleration_sessions": ACCELERATION_SESSIONS,
            "hot_now": hot_now,
            "sectors": ranked,
            "missing_symbols": [symbol for symbol in SECTOR_ETFS if symbol not in available],
        }
