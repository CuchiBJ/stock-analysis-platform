"""Faithful evidence serialization for the overview evolution series."""
import asyncio
from datetime import date, timedelta

from app.services.market_context_evolution import serialize_evolution


def test_evolution_keeps_missing_coverage_null_and_real_zero():
    as_of = date(2026, 10, 20)
    result = serialize_evolution([
        {"date": as_of - timedelta(days=1), "universe": 0,
         "breadth_ratio": None, "leader_count": 0},
        {"date": as_of, "universe": 10,
         "breadth_ratio": 0, "leader_count": 0},
    ], as_of)

    assert result == [
        {"date": "2026-10-19", "breadth_ratio": None, "leader_count": None},
        {"date": "2026-10-20", "breadth_ratio": 0, "leader_count": 0},
    ]


def test_evolution_is_sorted_bounded_and_excludes_future_or_invalid_rows():
    as_of = date(2026, 10, 20)
    rows = [
        {"date": as_of - timedelta(days=offset), "universe": 10,
         "breadth_ratio": 0.5, "leader_count": 2}
        for offset in range(22)
    ]
    rows.extend([
        {"date": as_of + timedelta(days=1), "universe": 10,
         "breadth_ratio": 1, "leader_count": 4},
        {"date": "2026-10-19", "universe": 10,
         "breadth_ratio": 1, "leader_count": 4},
    ])

    result = serialize_evolution(rows, as_of)

    assert len(result) == 20
    assert [row["date"] for row in result] == sorted(row["date"] for row in result)
    assert result[0]["date"] == "2026-10-01"
    assert result[-1]["date"] == "2026-10-20"


def test_engine_requests_twenty_grouped_sessions():
    from app.services.market_context_engine import MarketContextEngine

    class Engine(MarketContextEngine):
        def __init__(self):
            self.requested = None

        async def _daily_dimension_series(self, as_of, n):
            self.requested = (as_of, n)
            return [{"date": as_of, "universe": 10,
                     "breadth_ratio": 1, "leader_count": 2}]

    engine = Engine()
    as_of = date(2026, 10, 20)
    result = asyncio.run(engine.evolution_history(as_of))
    assert engine.requested == (as_of, 20)
    assert result == [{"date": "2026-10-20", "breadth_ratio": 1.0, "leader_count": 2}]


def test_evolution_rejects_invalid_metric_values():
    as_of = date(2026, 10, 20)
    result = serialize_evolution([
        {"date": as_of, "universe": 10, "breadth_ratio": 1.5,
         "leader_count": -1},
    ], as_of)
    assert result == [{"date": "2026-10-20", "breadth_ratio": None, "leader_count": None}]
