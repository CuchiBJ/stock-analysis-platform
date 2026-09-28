"""Reusable selector for the current Setup Feed snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics
from app.services.observation_scorer import (
    is_pre_reclaim_candidate,
    score_breakout_quality,
    score_observation_priority,
)
from app.services.transition_engine import OperationalTransition, TransitionEngine
from app.services.universe_filters import QUALITY_FILTERS


LIVE_INSTITUTIONAL_FILTERS = [
    *QUALITY_FILTERS,
    StockMetrics.perf_1y > 30,
    StockMetrics.current_price > StockMetrics.ema50,
    StockMetrics.current_price > StockMetrics.sma150,
    StockMetrics.sma150 > StockMetrics.sma200,
    StockMetrics.current_price >= StockMetrics.low_52w * 1.5,
    StockMetrics.distance_to_high_52w_atr >= -3.0,
]


def passes_ema_trigger(metrics: StockMetrics) -> bool:
    return any(
        value is not None and -1.0 <= value <= 0.5
        for value in (metrics.distance_to_ema9_atr, metrics.distance_to_ema21_atr)
    )


def passes_breakout_trigger(metrics: StockMetrics) -> bool:
    ema21 = metrics.distance_to_ema21_atr
    high52 = metrics.distance_to_high_52w_atr
    return ema21 is not None and high52 is not None and 0 < ema21 <= 1.5 and high52 >= -1.0


def distance_to_setup_pct(metrics: StockMetrics, transition: str) -> tuple[float | None, str]:
    d9, d21 = metrics.distance_to_ema9, metrics.distance_to_ema21
    if transition == "breakout":
        return (round(d21, 2) if d21 is not None else None, "EMA21")
    if transition == "entering_pullback" and d9 is not None and abs(d9) <= 0.5:
        return round(d9, 2), "EMA9"
    candidates = [(abs(value), value, label) for value, label in ((d9, "EMA9"), (d21, "EMA21")) if value is not None]
    if not candidates:
        return None, "EMA"
    _, value, label = min(candidates)
    return round(value, 2), label


def day_change_pct(current: StockMetrics, previous: StockMetrics | None) -> float | None:
    if previous is None or not previous.current_price or current.current_price is None:
        return None
    return round((current.current_price / previous.current_price - 1.0) * 100.0, 2)


def _severity(transition: OperationalTransition) -> str:
    if transition == OperationalTransition.FAILING:
        return "critical"
    if transition in (OperationalTransition.WEAKENING, OperationalTransition.DISTRIBUTION):
        return "negative"
    if transition == OperationalTransition.STABLE:
        return "neutral"
    return "positive"


def _direction(transition: OperationalTransition) -> str:
    if transition in (OperationalTransition.WEAKENING, OperationalTransition.DISTRIBUTION, OperationalTransition.FAILING):
        return "deteriorating"
    if transition == OperationalTransition.STABLE:
        return "stable"
    return "improving"


class LiveTransitionSelector:
    """Calculate exactly what the live Setup Feed shows for the current snapshot."""

    def __init__(self, db: AsyncSession, transition_engine: TransitionEngine | None = None):
        self.db = db
        self.transition_engine = transition_engine or TransitionEngine(db)

    async def select(self, limit: int = 10) -> list[dict[str, Any]]:
        latest_date = (await self.db.execute(select(func.max(StockMetrics.date)))).scalar()
        if latest_date is None:
            return []

        rows = (
            await self.db.execute(
                select(StockMetrics)
                .where(
                    and_(
                        StockMetrics.date >= latest_date - timedelta(days=7),
                        StockMetrics.date <= latest_date,
                        *LIVE_INSTITUTIONAL_FILTERS,
                    )
                )
                .order_by(StockMetrics.date.desc())
                .limit(1000)
            )
        ).scalars().all()

        by_symbol: dict[str, list[StockMetrics]] = {}
        for metrics in rows:
            by_symbol.setdefault(metrics.symbol, []).append(metrics)

        transitions: list[dict[str, Any]] = []
        for symbol, history in by_symbol.items():
            current = history[0]
            if current.date != latest_date:
                continue
            in_ema_zone = passes_ema_trigger(current)
            if not (in_ema_zone or passes_breakout_trigger(current)):
                continue

            previous = history[1] if len(history) >= 2 else None
            if previous is None:
                operational = type(
                    "StableTransition",
                    (),
                    {
                        "transition": OperationalTransition.STABLE,
                        "strength": 0.5,
                        "rs_change": 0.0,
                        "volume_change_pct": 0.0,
                        "narrative": "No previous data for comparison.",
                        "timestamp": datetime.utcnow(),
                    },
                )()
            else:
                operational = await self.transition_engine.calculate_operational_transition(symbol, current, previous)

            is_breakout = operational.transition == OperationalTransition.BREAKOUT
            if (not in_ema_zone and not is_breakout) or operational.transition == OperationalTransition.STABLE:
                continue

            setup_score = (
                round(score_breakout_quality(current), 1)
                if is_breakout
                else round(current.pullback_quality_score, 1)
                if current.pullback_quality_score is not None
                else None
            )
            distance, ema_label = distance_to_setup_pct(current, operational.transition.value)
            transitions.append(
                {
                    "symbol": symbol,
                    "transition": operational.transition.value,
                    "direction": _direction(operational.transition),
                    "strength": operational.strength,
                    "observation_priority": round(score_observation_priority(current), 1),
                    "pullback_quality_score": round(current.pullback_quality_score, 1) if current.pullback_quality_score is not None else None,
                    "setup_score": setup_score,
                    "is_pre_reclaim": is_pre_reclaim_candidate(current),
                    "timestamp": operational.timestamp.isoformat(),
                    "narrative": operational.narrative,
                    "severity": _severity(operational.transition),
                    "rs_change": getattr(operational, "rs_change", 0.0),
                    "volume_change_pct": getattr(operational, "volume_change_pct", 0.0),
                    "current_price": round(current.current_price, 2) if current.current_price else None,
                    "change_pct": day_change_pct(current, previous),
                    "dist_to_setup_pct": distance,
                    "dist_ema_label": ema_label,
                }
            )

        transitions.sort(
            key=lambda item: (
                item["setup_score"] or 0.0,
                item["transition"] == OperationalTransition.ENTERING_PULLBACK.value,
                item["is_pre_reclaim"],
                item["observation_priority"],
                item["strength"],
            ),
            reverse=True,
        )
        selected = transitions[:limit]
        if len(transitions) > limit:
            selected += [item for item in transitions[limit:] if item["transition"] == OperationalTransition.BREAKOUT.value]
        return selected

    async def current_symbols(self, limit: int = 20) -> set[str]:
        return {item["symbol"] for item in await self.select(limit=limit)}
