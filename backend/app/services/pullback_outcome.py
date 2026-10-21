"""Chronological outcomes for an EMA9/EMA21 support pullback."""
from __future__ import annotations

from math import isfinite
from typing import Protocol, Sequence, cast

PULLBACK_WINDOW_SESSIONS = 10
PULLBACK_CONTINUATION_ATR = 1.5


class PullbackSnapshot(Protocol):
    price_at_detection: float | None
    atr_at_detection: float | None
    ema9_at_detection: float | None
    ema21_at_detection: float | None
    ema50_at_detection: float | None


class DailyBar(Protocol):
    high: float
    low: float
    close: float


def _positive_finite(value: float | None) -> bool:
    return value is not None and isfinite(value) and value > 0


def classify_entering_pullback(
    snapshot: PullbackSnapshot, prices: Sequence[DailyBar]
) -> str:
    """Read ten completed bars in order, seeded by the detection snapshot.

    Support must precede continuation on a separate session. Invalidation
    anywhere in the full window overrides an earlier continuation.
    """
    seeds = (
        snapshot.price_at_detection,
        snapshot.atr_at_detection,
        snapshot.ema9_at_detection,
        snapshot.ema21_at_detection,
        snapshot.ema50_at_detection,
    )
    if not all(_positive_finite(value) for value in seeds):
        return "INSUFFICIENT_DATA"

    window = prices[:PULLBACK_WINDOW_SESSIONS]
    for bar in window:
        if not all(_positive_finite(value) for value in (bar.low, bar.high, bar.close)):
            return "INSUFFICIENT_DATA"
        if not bar.low <= bar.close <= bar.high:
            return "INSUFFICIENT_DATA"

    if len(window) < PULLBACK_WINDOW_SESSIONS:
        return "PENDING"

    # Every seed is a positive finite float after the validation above.
    price, atr, ema9, ema21, ema50 = (cast(float, value) for value in seeds)
    target = price + PULLBACK_CONTINUATION_ATR * atr
    support_session = None
    continued = False

    for session, bar in enumerate(window):
        ema9 += (bar.close - ema9) * (2 / 10)
        ema21 += (bar.close - ema21) * (2 / 22)
        ema50 += (bar.close - ema50) * (2 / 51)

        if bar.low <= ema50 or bar.close < ema21:
            return "FAILURE"

        if (
            support_session is not None
            and session > support_session
            and bar.high >= target
            and bar.close >= ema9
        ):
            continued = True

        recovered_ema9 = bar.low <= ema9 and bar.close >= ema9
        recovered_ema21 = bar.low <= ema21 and bar.close >= ema21
        if support_session is None and (recovered_ema9 or recovered_ema21):
            support_session = session

    return "SUCCESS" if continued else "NEUTRAL"
