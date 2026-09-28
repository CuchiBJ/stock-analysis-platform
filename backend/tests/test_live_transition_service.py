import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch
from datetime import date, timedelta

from app.services.live_transition_service import LiveTransitionSelector
from app.services.transition_engine import OperationalTransition


class Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


def candidate(symbol, score, *, day=date(2026, 9, 24), high_distance=-1.0):
    return SimpleNamespace(
        symbol=symbol,
        date=day,
        distance_to_ema9_atr=0.0,
        distance_to_ema21_atr=0.2,
        distance_to_high_52w_atr=high_distance,
        pullback_quality_score=score,
        current_price=100.0,
        distance_to_ema9=0.0,
        distance_to_ema21=0.4,
    )


def operational(kind, strength):
    return SimpleNamespace(
        transition=kind,
        strength=strength,
        rs_change=1.0,
        volume_change_pct=-10.0,
        narrative=f"{kind.value} narrative",
        timestamp=SimpleNamespace(isoformat=lambda: "2026-09-24T20:00:00"),
    )


def test_current_symbols_uses_current_selector_not_observation_history():
    selector = LiveTransitionSelector(AsyncMock())
    selector.select = AsyncMock(return_value=[{"symbol": "BE"}, {"symbol": "DOCN"}])
    assert asyncio.run(selector.current_symbols()) == {"BE", "DOCN"}
    selector.select.assert_awaited_once_with(limit=20)


def test_selector_returns_empty_without_metrics():
    result = SimpleNamespace(scalar=lambda: None)
    db = AsyncMock()
    db.execute.return_value = result
    assert asyncio.run(LiveTransitionSelector(db).select()) == []


def test_selector_preserves_feed_order_fields_limit_and_breakout_append():
    today = date(2026, 9, 24)
    yesterday = today - timedelta(days=1)
    high = candidate("HIGH", 82.0)
    breakout = candidate("BRK", 40.0, high_distance=-0.5)
    low = candidate("LOW", 58.0)
    history = [
        high, breakout, low,
        candidate("HIGH", 76.0, day=yesterday),
        candidate("BRK", 40.0, day=yesterday),
        candidate("LOW", 60.0, day=yesterday),
    ]
    db = AsyncMock()
    db.execute.side_effect = [Result(scalar=today), Result(rows=history)]
    engine = SimpleNamespace(calculate_operational_transition=AsyncMock(side_effect=[
        operational(OperationalTransition.ENTERING_PULLBACK, 0.8),
        operational(OperationalTransition.BREAKOUT, 0.9),
        operational(OperationalTransition.COMPRESSING, 0.6),
    ]))
    with patch("app.services.live_transition_service.score_observation_priority", return_value=50.0), patch("app.services.live_transition_service.score_breakout_quality", return_value=40.0), patch("app.services.live_transition_service.is_pre_reclaim_candidate", return_value=False):
        rows = asyncio.run(LiveTransitionSelector(db, engine).select(limit=1))

    assert [row["symbol"] for row in rows] == ["HIGH", "BRK"]
    assert set(rows[0]) == {
        "symbol", "transition", "direction", "strength", "observation_priority",
        "pullback_quality_score", "setup_score", "is_pre_reclaim", "timestamp",
        "narrative", "severity", "rs_change", "volume_change_pct", "current_price",
        "change_pct", "dist_to_setup_pct", "dist_ema_label",
    }
