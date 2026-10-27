"""Synthetic database evidence for the additive market context page."""
import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.stock import Stock, StockMetrics, StockPrice
from app.services import market_context_overview as service
from tests.test_market_context_breadth import AsyncSessionShim


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    for model in (Stock, StockMetrics, StockPrice):
        model.__table__.create(engine)
    service._cache.clear()
    with Session(engine) as session:
        yield session
    service._cache.clear()
    engine.dispose()


def price(symbol, day, close):
    return StockPrice(symbol=symbol, date=day, open=close, high=close, low=close,
                      close=close, volume=100)


def test_dated_indices_exclude_future_metrics_and_prices(db):
    day = date(2026, 10, 20)
    db.add_all([
        price("SPY", day - timedelta(days=2), 100),
        price("SPY", day - timedelta(days=1), 110),
        price("SPY", day + timedelta(days=1), 999),
        StockMetrics(symbol="SPY", date=day - timedelta(days=3), ema50=90,
                     ema200=80, sma150=95, sma200=85, high_52w=120),
        StockMetrics(symbol="SPY", date=day, ema50=900, ema200=800),
    ])
    db.commit()
    result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "SPY", day))
    assert result == {
        "symbol": "SPY", "date": "2026-10-19", "previous_date": "2026-10-18",
        "previous_price": 100, "metrics_date": "2026-10-17",
        "price": 110, "change_pct": pytest.approx(10), "trend": "alcista",
        "above_ema50": True, "above_ema200": True, "new_high_52w": False,
    }


def test_missing_benchmark_and_partial_metrics_remain_unknown(db):
    day = date(2026, 10, 20)
    absent = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "SPY", day))
    assert absent["symbol"] == "SPY"
    assert all(value is None for key, value in absent.items() if key != "symbol")
    db.add_all([price("QQQ", day, 100),
                StockMetrics(symbol="QQQ", date=day, ema50=90, ema200=0)])
    db.commit()
    result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "QQQ", day))
    assert result["above_ema50"] is True
    for key in ("change_pct", "above_ema200", "new_high_52w", "trend"):
        assert result[key] is None


def test_overview_cache_expires_is_bounded_and_does_not_alias(db, monkeypatch):
    day = date(2026, 10, 20)
    now = [0]
    monkeypatch.setattr(service, "monotonic", lambda: now[0])
    shim = AsyncSessionShim(db)
    result = asyncio.run(service.get_overview_evidence(shim, day))
    assert result["extremes"]["sectors"] == []
    assert result["extremes"]["up_ratio"] is None
    assert [index["symbol"] for index in result["indices"]] == ["SPY", "QQQ"]
    result["indices"][0]["price"] = 123
    cached = asyncio.run(service.get_overview_evidence(None, day))
    assert cached["indices"][0]["price"] is None
    db.add(price("SPY", day, 500))
    db.commit()
    now[0] = 301
    refreshed = asyncio.run(service.get_overview_evidence(shim, day))
    assert refreshed["indices"][0]["price"] == 500
    for offset in range(1, 6):
        asyncio.run(service.get_overview_evidence(shim, day + timedelta(days=offset)))
    assert len(service._cache) == service._CACHE_LIMIT
    assert day not in service._cache


def test_overview_serialization_reuses_dated_evidence_not_live_index(monkeypatch):
    from app.api.v1.endpoints import market_context as endpoint
    from app.services.market_context_engine import MarketContext, ParticipationAnalysis, LeadershipAnalysis
    day = date(2026, 10, 20)
    ctx = MarketContext(as_of=day, universe_size=0,
                        participation=ParticipationAnalysis("STABLE", 0, 0, {}, {}),
                        leadership=LeadershipAnalysis("HEALTHY", 0, {}), engines_pending=[])

    class Engine:
        def __init__(self, db):
            pass

        async def analyze(self):
            return ctx

        async def evolution_history(self, as_of):
            assert as_of == day
            return [{"date": day.isoformat(), "breadth_ratio": None, "leader_count": None}]

    async def evidence(db, as_of):
        assert as_of == day
        return {"indices": [{"symbol": "SPY", "price": 100, "date": "2026-10-20",
                             "previous_date": "2026-10-19", "previous_price": 99,
                             "metrics_date": None}],
                "breadth": {"fresh": True}, "extremes": {"sectors": []}}

    async def forbidden(db):
        raise AssertionError("Overview must never query a live index")

    monkeypatch.setattr(endpoint, "MarketContextEngine", Engine)
    async def observe(*args):
        return True
    async def history(*args):
        return {"status": "available", "records": []}
    monkeypatch.setattr(endpoint.market_posture_record_service, "observe", observe)
    monkeypatch.setattr(endpoint.market_posture_record_service, "history", history)
    monkeypatch.setattr(endpoint, "_build_index_block", forbidden)
    monkeypatch.setattr(service, "get_overview_evidence", evidence)
    result = asyncio.run(endpoint.get_market_context_overview(object()))
    assert result["context"]["index"] == {"symbol": "SPY", "price": 100}
    assert result["context"]["participation"]["breadth_comparisons"] == {"fresh": True}
    assert result["evolution"] == [{"date": day.isoformat(), "breadth_ratio": None, "leader_count": None}]
    assert ctx.participation.breadth_comparisons == {}
    assert result["posture_history"] == {"status": "available", "records": []}


def test_overview_requests_only_exact_spy_reference_dates_and_current_body_is_unchanged(monkeypatch):
    from app.api.v1.endpoints import market_context as endpoint
    from app.services.market_context_engine import MarketContext, ParticipationAnalysis, LeadershipAnalysis
    day = date(2026, 10, 20)
    ctx = MarketContext(as_of=day, universe_size=0,
                        participation=ParticipationAnalysis("STABLE", 0, 0, {}, {}),
                        leadership=LeadershipAnalysis("HEALTHY", 0, {}), engines_pending=[])
    class Engine:
        def __init__(self, db): pass
        async def analyze(self): return ctx
        async def evolution_history(self, as_of): return []
    async def evidence(db, as_of):
        return {"indices": [{"symbol": "SPY", "date": "2026-10-20",
                              "previous_date": "2026-10-19", "price": None}],
                "breadth": {}, "extremes": {}}
    calls = []
    async def observe(db, session_date, posture):
        calls.append(("observe", session_date, posture))
        return True
    async def history(db, dates):
        calls.append(("history", dates))
        return {"status": "available", "records": []}
    monkeypatch.setattr(endpoint, "MarketContextEngine", Engine)
    monkeypatch.setattr(endpoint, "get_overview_evidence", evidence, raising=False)
    from app.services import market_context_overview
    monkeypatch.setattr(market_context_overview, "get_overview_evidence", evidence)
    monkeypatch.setattr(endpoint.market_posture_record_service, "observe", observe)
    monkeypatch.setattr(endpoint.market_posture_record_service, "history", history)
    overview = asyncio.run(endpoint.get_market_context_overview(object()))
    assert calls[0][0:2] == ("observe", day)
    assert calls[1] == ("history", [day, date(2026, 10, 19)])
    assert "posture_history" in overview

    async def index(db): return None
    monkeypatch.setattr(endpoint, "_build_index_block", index)
    current = asyncio.run(endpoint.get_current_market_context(object()))
    assert "posture_history" not in current
    assert current["as_of"] == day.isoformat()


@pytest.mark.parametrize(("spy_date", "previous_date"), [
    ("2026-10-19", "2026-10-18"),  # stale SPY: retain the actual context date only
    ("2026-10-20", "2026-10-20"),  # previous date cannot equal as_of
    ("2026-10-20", "2026-10-21"),  # previous date cannot be in the future
])
def test_overview_never_substitutes_or_reads_non_prior_spy_dates(
    monkeypatch, spy_date, previous_date,
):
    from app.api.v1.endpoints import market_context as endpoint
    from app.services.market_context_engine import MarketContext, ParticipationAnalysis, LeadershipAnalysis
    day = date(2026, 10, 20)
    ctx = MarketContext(as_of=day, universe_size=0,
                        participation=ParticipationAnalysis("STABLE", 0, 0, {}, {}),
                        leadership=LeadershipAnalysis("HEALTHY", 0, {}), engines_pending=[])

    class Engine:
        def __init__(self, db): pass
        async def analyze(self): return ctx
        async def evolution_history(self, as_of): return []

    async def evidence(db, as_of):
        return {"indices": [{"symbol": "SPY", "date": spy_date,
                              "previous_date": previous_date, "price": 100}],
                "breadth": {}, "extremes": {}}

    requested_dates = []
    async def observe(db, session_date, posture): return True
    async def history(db, dates):
        requested_dates.extend(dates)
        return {"status": "available", "records": []}

    from app.services import market_context_overview
    monkeypatch.setattr(endpoint, "MarketContextEngine", Engine)
    monkeypatch.setattr(market_context_overview, "get_overview_evidence", evidence)
    monkeypatch.setattr(endpoint.market_posture_record_service, "observe", observe)
    monkeypatch.setattr(endpoint.market_posture_record_service, "history", history)
    result = asyncio.run(endpoint.get_market_context_overview(object()))
    assert requested_dates == [day]
    assert result["posture_history"] == {"status": "available", "records": []}


def test_overview_returns_unavailable_history_when_observation_write_fails(monkeypatch):
    from app.api.v1.endpoints import market_context as endpoint
    from app.services.market_context_engine import MarketContext, ParticipationAnalysis, LeadershipAnalysis
    day = date(2026, 10, 20)
    ctx = MarketContext(as_of=day, universe_size=0,
                        participation=ParticipationAnalysis("STABLE", 0, 0, {}, {}),
                        leadership=LeadershipAnalysis("HEALTHY", 0, {}), engines_pending=[])
    class Engine:
        def __init__(self, db): pass
        async def analyze(self): return ctx
        async def evolution_history(self, as_of): return []
    async def evidence(db, as_of):
        return {"indices": [{"symbol": "SPY", "date": day.isoformat(),
                              "previous_date": "2026-10-19", "price": 100}],
                "breadth": {}, "extremes": {}}
    async def observe(db, session_date, posture): return False
    async def forbidden_history(*args): raise AssertionError("failed capture must suppress history")
    from app.services import market_context_overview
    monkeypatch.setattr(endpoint, "MarketContextEngine", Engine)
    monkeypatch.setattr(market_context_overview, "get_overview_evidence", evidence)
    monkeypatch.setattr(endpoint.market_posture_record_service, "observe", observe)
    monkeypatch.setattr(endpoint.market_posture_record_service, "history", forbidden_history)
    result = asyncio.run(endpoint.get_market_context_overview(object()))
    assert result["posture_history"] == {"status": "unavailable", "records": []}


def test_new_routes_inherit_authentication():
    async def check():
        from app.api.v1.api import api_router
        from app.core.auth import require_protected_request
        for path in ("/market-context/current", "/market-context/overview", "/market-context/volatility"):
            route = next(route for route in api_router.routes if route.path == path)
            assert any(dependency.call is require_protected_request for dependency in route.dependant.dependencies)

    asyncio.run(check())


def test_sector_constituents_are_sorted_and_totals_reconcile(db):
    from app.services.market_context_breadth import calculate_breadth_comparisons
    day = date(2026, 10, 20)
    for symbol, sector in (("ZZZ", "Technology"), ("AAA", "Technology"), ("BOTH", None)):
        db.add(Stock(symbol=symbol, name=f"Name {symbol}", sector=sector, market_cap=700_000_000))
        db.add(StockMetrics(symbol=symbol, date=day, current_price=10,
                            avg_volume_10d=900_000, adr_percent=5))
        for offset in range(1, 253):
            db.add(StockPrice(symbol=symbol, date=day - timedelta(days=offset),
                              open=10, high=12, low=8, close=10, volume=100))
        db.add(StockPrice(symbol=symbol, date=day, open=10, high=13,
                          low=7 if symbol == "BOTH" else 8, close=10, volume=100))
    for offset in range(1, 253):
        db.add(price("SPY", day - timedelta(days=offset), 500))
    db.commit()
    breadth = asyncio.run(calculate_breadth_comparisons(AsyncSessionShim(db), day,
                                                       include_constituents=True))
    extremes = breadth["new_session_highs_vs_lows"]
    assert [group["sector"] for group in extremes["sectors"]] == ["Sin sector", "Technology"]
    assert [stock["symbol"] for stock in extremes["sectors"][1]["highs"]] == ["AAA", "ZZZ"]
    assert extremes["sectors"][0]["lows"] == [{"symbol": "BOTH", "name": "Name BOTH"}]
    assert sum(len(group["highs"]) for group in extremes["sectors"]) == extremes["up_count"] == 3
    assert sum(len(group["lows"]) for group in extremes["sectors"]) == extremes["down_count"] == 1


def test_unauthenticated_overview_and_volatility_are_rejected():
    async def check():
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
        from app.api.v1.api import api_router
        from app.core.deps import get_db

        app = FastAPI()
        app.include_router(api_router)

        async def fixture_db():
            # Missing cookies must be rejected before any database query.
            yield object()

        app.dependency_overrides[get_db] = fixture_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for url in ("/market-context/current", "/market-context/overview",
                        "/market-context/volatility?as_of=2026-10-20"):
                response = await client.get(url)
                assert response.status_code == 401

    asyncio.run(check())


@pytest.mark.parametrize("with_calendar", [False, True])
def test_daily_change_requires_the_previous_market_session(db, with_calendar):
    day = date(2026, 10, 20)
    db.add_all([price("QQQ", day, 110), price("QQQ", day - timedelta(days=2), 100)])
    if with_calendar:
        db.add_all([price("SPY", day, 500), price("SPY", day - timedelta(days=1), 490),
                    price("SPY", day - timedelta(days=2), 480)])
    db.commit()
    result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "QQQ", day))
    assert result["price"] == 110
    assert result["change_pct"] is None
    if with_calendar:
        db.add(price("QQQ", day - timedelta(days=1), 105))
        db.commit()
        result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "QQQ", day))
        assert result["change_pct"] == pytest.approx((110 / 105 - 1) * 100)
        assert result["previous_date"] == (day - timedelta(days=1)).isoformat()
        assert result["previous_price"] == 105


def test_previous_benchmark_fields_use_immediate_stored_spy_session(db):
    day = date(2026, 10, 20)
    db.add_all([price("SPY", day, 510), price("SPY", day - timedelta(days=2), 490),
                price("QQQ", day, 210), price("QQQ", day - timedelta(days=2), 190)])
    db.commit()
    result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "QQQ", day))
    assert result["date"] == day.isoformat()
    assert result["previous_date"] == (day - timedelta(days=2)).isoformat()
    assert result["previous_price"] == 190
    assert result["change_pct"] == pytest.approx((210 / 190 - 1) * 100)


def test_qqq_overview_uses_dated_price_previous_session_and_metrics(db):
    day = date(2026, 10, 23)
    previous_day = date(2026, 10, 22)
    db.add_all([
        price("SPY", day, 510),
        price("SPY", previous_day, 500),
        price("QQQ", day, 210),
        price("QQQ", previous_day, 200),
        StockMetrics(symbol="QQQ", date=day, ema50=205, ema200=190,
                     sma150=195, sma200=185, high_52w=215),
    ])
    db.commit()

    result = asyncio.run(service.build_dated_index(AsyncSessionShim(db), "QQQ", day))

    assert result["date"] == day.isoformat()
    assert result["previous_date"] == previous_day.isoformat()
    assert result["previous_price"] == 200
    assert result["price"] == 210
    assert result["change_pct"] == pytest.approx(5)
    assert result["metrics_date"] == day.isoformat()
    assert result["above_ema50"] is True
