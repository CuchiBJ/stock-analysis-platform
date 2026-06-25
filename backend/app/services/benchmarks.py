"""Benchmark / index identification — single source of truth.

The platform evaluates individual stocks as institutional swing-momentum
setups. Broad-market index ETFs are NOT setups: they are reference
instruments (the RS baseline, a regime proxy). Judging them with the
Minervini leader gate ("up >30% YoY, ADR≥4%, Stage 2 leader") brands them
as "broken structure", which is conceptually wrong.

These are exactly the symbols enumerated in the `indices` table
(app/models/index.py).
"""
from __future__ import annotations

from typing import Optional

BENCHMARK_SYMBOLS = frozenset({"SPY", "QQQ", "IWM", "DIA"})


def is_benchmark(symbol: Optional[str]) -> bool:
    """True for broad-market benchmark indices (SPY, QQQ, IWM, DIA)."""
    return bool(symbol) and symbol.upper() in BENCHMARK_SYMBOLS


def compute_index_trend(
    price: Optional[float],
    ema50: Optional[float],
    ema200: Optional[float],
    sma150: Optional[float],
    sma200: Optional[float],
) -> str:
    """Trend read for an index against its OWN moving averages.

    "alcista"  — price above EMA50 and EMA200 with SMA150 > SMA200
    "bajista"  — price below EMA200 with SMA150 < SMA200
    "lateral"  — anything in between (or missing inputs)
    """
    above_ema50 = price is not None and ema50 is not None and price > ema50
    above_ema200 = price is not None and ema200 is not None and price > ema200
    below_ema200 = price is not None and ema200 is not None and price < ema200
    ma_stack_up = sma150 is not None and sma200 is not None and sma150 > sma200
    ma_stack_down = sma150 is not None and sma200 is not None and sma150 < sma200

    if above_ema50 and above_ema200 and ma_stack_up:
        return "alcista"
    if below_ema200 and ma_stack_down:
        return "bajista"
    return "lateral"
