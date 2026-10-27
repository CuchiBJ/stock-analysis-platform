"""Synthetic tests for bulk sector previous-session extreme history."""
import asyncio
from datetime import date, timedelta
from math import inf

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.stock import Stock, StockMetrics, StockPrice
from app.services import market_context_sector_evolution as service
from app.services.market_context_breadth import calculate_breadth_comparisons
from tests.test_market_context_breadth import AsyncSessionShim


@pytest.fixture(autouse=True)
def clear_history_cache():
    service._cache.clear()
    yield
    service._cache.clear()


def _price(symbol, day, high=10, low=5):
    return StockPrice(symbol=symbol, date=day, open=8, high=high, low=low,
                      close=8, volume=1_000_000)


def _metrics(symbol, day):
    return StockMetrics(symbol=symbol, date=day, avg_volume_10d=900_000,
                        current_price=10, adr_percent=5)


def _db():
    engine = create_engine("sqlite:///:memory:")
    for model in (Stock, StockMetrics, StockPrice):
        model.__table__.create(engine)
    return engine


def test_sector_history_exact_window_events_gaps_orphans_and_reconciliation():
    engine = _db()
    as_of = date(2026, 10, 22)
    dates = [as_of - timedelta(days=256 - i) for i in range(257)]
    with Session(engine) as db:
        db.add_all([
            Stock(symbol="BOTH", name="Both", sector="Technology", market_cap=700_000_000),
            Stock(symbol="ZERO", name="Zero", sector="Technology", market_cap=700_000_000),
            Stock(symbol="GAP", name="Gap", sector="Excluded only", market_cap=700_000_000),
            Stock(symbol="INVALID", name="Invalid", sector="Excluded only", market_cap=700_000_000),
        ])
        for day in dates:
            db.add(_price("SPY", day, 500, 400))
            for symbol in ("BOTH", "ZERO", "GAP", "INVALID"):
                if day == as_of:
                    continue
                if symbol != "GAP" or day != dates[-2]:
                    db.add(_price(symbol, day))
        # The missing immediately preceding row excludes GAP; malformed current
        # high/low excludes INVALID. BOTH hits both sides and ZERO is a real zero.
        db.add_all([
            _price("BOTH", as_of, 11, 4), _price("ZERO", as_of, 10, 5),
            _price("INVALID", as_of, inf, 5),
            _price("BOTH", as_of + timedelta(days=1), 999, 1),
            _price("ORPHAN", as_of - timedelta(days=257), 999, 1),
        ])
        for day in dates[-5:]:
            if day == dates[-2]:
                continue  # a stored session with missing metrics is retained empty
            for symbol in ("BOTH", "ZERO", "GAP", "INVALID"):
                db.add(_metrics(symbol, day))
        db.commit()
        shim = AsyncSessionShim(db)
        result = asyncio.run(service.get_sector_evolution(shim, as_of))
        assert len(shim.statements) == 3
        assert result["status"] == "available"
        assert [session["date"] for session in result["sessions"]] == [
            day.isoformat() for day in dates[-5:]
        ]
        assert result["sessions"][3]["sectors"] == []
        current = result["sessions"][-1]
        assert current == {
            "date": as_of.isoformat(), "eligible_symbols": 2, "excluded_symbols": 2,
            "high_count": 1, "low_count": 1,
            "sectors": [
                {"sector": "Excluded only", "eligible_symbols": 0, "excluded_symbols": 2,
                 "high_count": 0, "low_count": 0},
                {"sector": "Technology", "eligible_symbols": 2, "excluded_symbols": 0,
                 "high_count": 1, "low_count": 1},
            ],
        }
        breadth = asyncio.run(calculate_breadth_comparisons(shim, as_of, include_constituents=True))
        extremes = breadth["new_session_highs_vs_lows"]
        assert current["eligible_symbols"] == extremes["eligible_symbols"]
        assert current["excluded_symbols"] == extremes["excluded_symbols"]
        assert current["high_count"] == extremes["up_count"]
        assert current["low_count"] == extremes["down_count"]
        assert [(s["sector"], s["eligible_symbols"], s["excluded_symbols"],
                 s["high_count"], s["low_count"]) for s in current["sectors"]] == [
            (s["sector"], s["eligible_symbols"], s["excluded_symbols"], len(s["highs"]), len(s["lows"]))
            for s in extremes["sectors"]
        ]
    engine.dispose()


def test_missing_reference_and_cache_copy_ttl_and_bound(monkeypatch):
    engine = _db()
    now = [0.0]
    monkeypatch.setattr(service, "monotonic", lambda: now[0])
    service._cache.clear()
    with Session(engine) as db:
        shim = AsyncSessionShim(db)
        missing = asyncio.run(service.get_sector_evolution(shim, date(2026, 10, 22)))
        assert missing == {"as_of": "2026-10-22", "status": "no_reference_session", "sessions": []}
        service._cache.clear()
        for offset in range(6):
            day = date(2026, 10, 1) + timedelta(days=offset)
            db.add(_price("SPY", day))
        db.commit()
        one = asyncio.run(service.get_sector_evolution(shim, date(2026, 10, 1)))
        one["sessions"].append({"corrupt": True})
        again = asyncio.run(service.get_sector_evolution(None, date(2026, 10, 1)))
        assert len(again["sessions"]) == 1
        assert len(service._cache) == 1
        for offset in range(1, 6):
            asyncio.run(service.get_sector_evolution(shim, date(2026, 10, 1) + timedelta(days=offset)))
        assert len(service._cache) == service._CACHE_LIMIT
        now[0] = service._CACHE_TTL + 1
        asyncio.run(service.get_sector_evolution(shim, date(2026, 10, 1)))
    engine.dispose()
    service._cache.clear()


def test_sector_evolution_route_is_protected():
    async def check():
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from app.api.v1.api import api_router
        from app.core.deps import get_db

        app = FastAPI()
        app.include_router(api_router)

        async def fixture_db():
            yield object()

        app.dependency_overrides[get_db] = fixture_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/market-context/sector-evolution?as_of=2026-10-22")
            assert response.status_code == 401

    asyncio.run(check())


def test_each_session_rolls_its_own_window_and_quality_population():
    engine = _db()
    as_of = date(2026, 10, 22)
    dates = [as_of - timedelta(days=2 * (256 - i)) for i in range(257)]
    with Session(engine) as db:
        db.add_all([
            Stock(symbol="ROLL", name="Roll", sector=None, market_cap=700_000_000),
            Stock(symbol="GAP", name="Gap", sector="Coverage", market_cap=700_000_000),
            Stock(symbol="SMALL", name="Small", sector="Excluded cap", market_cap=100_000_000),
        ])
        for i, day in enumerate(dates):
            db.add(_price("SPY", day))
            db.add(_price("ROLL", day, 100 if i == 0 else 11 + i - 252 if i >= 252 else 10))
            if i != 1:
                db.add(_price("GAP", day))
        for i, day in enumerate(dates[-5:]):
            metric = _metrics("ROLL", day)
            if i == 1:
                metric.adr_percent = 3
            db.add_all([metric, _metrics("GAP", day), _metrics("SMALL", day)])
        db.add(_price("ROLL", as_of - timedelta(days=1), 999))
        db.add(_price("SPY", as_of + timedelta(days=2)))
        db.commit()
        shim = AsyncSessionShim(db)
        result = asyncio.run(service.get_sector_evolution(shim, as_of))
        assert len(shim.statements) == 3
        first, second, _, _, last = result["sessions"]
        assert first["high_count"] == 1
        assert first["eligible_symbols"] == 2
        assert first["excluded_symbols"] == 0
        assert all(s["sector"] != "Sin sector" for s in second["sectors"])
        assert last["high_count"] == 1
        assert last["eligible_symbols"] == 2
        assert last["excluded_symbols"] == 0
        assert last["date"] == as_of.isoformat()
        assert all(s["sector"] != "Excluded cap" for d in result["sessions"] for s in d["sectors"])
    engine.dispose()
