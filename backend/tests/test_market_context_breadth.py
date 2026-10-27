"""Database-backed tests for Market Context's batched OHLC breadth query."""
from datetime import date, timedelta
from math import inf
import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.stock import Stock, StockMetrics, StockPrice
from app.models.user import User  # noqa: F401 — registers JournalTrade's relationship target
from app.services.market_context_engine import (
    LeadershipAnalysis,
    MarketContext,
    ParticipationAnalysis,
)
from app.services.market_context_breadth import calculate_breadth_comparisons


class AsyncSessionShim:
    """Adapt a real synchronous SQLite session to the service's execute await."""

    def __init__(self, session: Session):
        self.session = session
        self.statements = []

    async def execute(self, statement):
        self.statements.append(str(statement))
        return self.session.execute(statement)


def test_breadth_counts_boundaries_filters_and_previous_spy_session():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    StockMetrics.__table__.create(engine)
    StockPrice.__table__.create(engine)
    as_of = date(2026, 10, 20)
    dates = [as_of - timedelta(days=253 - i) for i in range(252)]

    with Session(engine) as db:
        symbols = [
            "BOTH", "DOWN", "TIE", "GAP", "INVALID", "BROKEN", "BADHIST",
            "NO_CURRENT", "ZERO_PREV", "NEG_PREV", "STALE", "UNQUALIFIED",
        ]
        sectors = {
            "BOTH": "Technology", "DOWN": "Health Care", "TIE": "Utilities",
            "GAP": "Excluded only", "STALE": "Excluded only",
            "INVALID": "Excluded only", "BROKEN": "Excluded only",
            "BADHIST": "Excluded only", "NO_CURRENT": "Excluded only",
            "ZERO_PREV": "", "NEG_PREV": None, "UNQUALIFIED": "Outside universe",
        }
        db.add_all(
            Stock(symbol=symbol, name=symbol, sector=sectors[symbol], market_cap=700_000_000)
            for symbol in symbols
        )
        for symbol in symbols:
            qualified = symbol != "UNQUALIFIED"
            db.add(StockMetrics(
                symbol=symbol, date=as_of, avg_volume_10d=900_000,
                current_price=10, adr_percent=5 if qualified else 3,
            ))
            for i, session_date in enumerate(dates):
                if symbol == "STALE" and i == 251:
                    continue
                if symbol == "GAP" and i == 251:
                    continue
                db.add(StockPrice(
                    symbol=symbol, date=session_date, open=10,
                    high=0 if symbol == "BADHIST" and i == 251 else 10,
                    low=5,
                    close=(10 if symbol == "BOTH" else 0 if symbol == "ZERO_PREV" else -5 if symbol == "NEG_PREV" else 5) if i == 251 else 10,
                    volume=1_000_000,
                ))
        # SPY defines the market-session calendar. An orphan row in the gap
        # before as_of must not displace SPY's latest session.
        db.add_all(
            StockPrice(symbol="SPY", date=session_date, open=500, high=501, low=499, close=500, volume=1)
            for session_date in dates
        )
        # The symbol is missing the required previous session and cannot
        # become eligible by reaching farther back to an older row.
        db.add_all([
            StockPrice(symbol="BOTH", date=as_of, open=10, high=10.01, low=4.99, close=10.4, volume=100),
            StockPrice(symbol="DOWN", date=as_of, open=5, high=10, low=5, close=4.8, volume=100),
            StockPrice(symbol="TIE", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="GAP", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="STALE", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="INVALID", date=as_of, open=5, high=inf, low=5, close=5, volume=100),
            StockPrice(symbol="BROKEN", date=as_of, open=5, high=4, low=5, close=5, volume=100),
            StockPrice(symbol="BADHIST", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="ZERO_PREV", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="NEG_PREV", date=as_of, open=5, high=10, low=5, close=5, volume=100),
            StockPrice(symbol="UNQUALIFIED", date=as_of, open=5, high=20, low=1, close=5, volume=100),
            # Future rows must not affect the as_of analysis or become a prior session.
            StockPrice(symbol="BOTH", date=as_of + timedelta(days=1), open=1, high=99, low=1, close=99, volume=100),
            StockPrice(symbol="ORPHAN", date=as_of - timedelta(days=1), open=1, high=1, low=1, close=1, volume=1),
        ])
        # Older rows cannot substitute for a missing global session.
        db.add(StockPrice(
            symbol="GAP", date=dates[0] - timedelta(days=1), open=10,
            high=10, low=5, close=10, volume=1_000_000,
        ))
        db.commit()

        default_db = AsyncSessionShim(db)
        detail_db = AsyncSessionShim(db)
        result = asyncio.run(calculate_breadth_comparisons(default_db, as_of))
        detail = asyncio.run(calculate_breadth_comparisons(detail_db, as_of, include_constituents=True))
        assert not any("stocks.sector" in statement for statement in default_db.statements)
        assert sum("stocks.sector" in statement for statement in detail_db.statements) == 1
        sectors = detail["new_session_highs_vs_lows"].pop("sectors")
        assert sectors == [
            {"sector": "Excluded only", "highs": [], "lows": [], "eligible_symbols": 0, "excluded_symbols": 6},
            {"sector": "Health Care", "highs": [], "lows": [], "eligible_symbols": 1, "excluded_symbols": 0},
            {"sector": "Sin sector", "highs": [], "lows": [], "eligible_symbols": 2, "excluded_symbols": 0},
            {"sector": "Technology", "highs": [{"symbol": "BOTH", "name": "BOTH"}],
             "lows": [{"symbol": "BOTH", "name": "BOTH"}], "eligible_symbols": 1, "excluded_symbols": 0},
            {"sector": "Utilities", "highs": [], "lows": [], "eligible_symbols": 1, "excluded_symbols": 0},
        ]
        assert detail == result

    extremes = result["new_session_highs_vs_lows"]
    assert result["date"] == as_of.isoformat()
    assert extremes == {
        "up_count": 1, "down_count": 1, "eligible_symbols": 5,
        "excluded_symbols": 6, "up_ratio": 0.5,
    }
    assert sum(sector["eligible_symbols"] for sector in sectors) == extremes["eligible_symbols"]
    assert sum(sector["excluded_symbols"] for sector in sectors) == extremes["excluded_symbols"]
    assert sum(len(sector["highs"]) for sector in sectors) == extremes["up_count"]
    assert sum(len(sector["lows"]) for sector in sectors) == extremes["down_count"]
    opening = result["up_from_open_vs_down"]
    assert opening["up_count"] == 1
    assert opening["down_count"] == 1
    assert opening["eligible_symbols"] == 10
    assert opening["excluded_symbols"] == 1
    move = result["up_4pct_vs_down_4pct"]
    assert move["up_count"] == 1
    assert move["down_count"] == 1
    assert move["eligible_symbols"] == 6
    assert move["excluded_symbols"] == 5


def test_zero_events_have_null_ratio_and_missing_current_prices_reduce_coverage():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    StockMetrics.__table__.create(engine)
    StockPrice.__table__.create(engine)
    as_of = date(2026, 10, 20)
    dates = [as_of - timedelta(days=253 - i) for i in range(252)]
    with Session(engine) as db:
        db.add(Stock(symbol="FLAT", name="Flat", market_cap=700_000_000))
        db.add(StockMetrics(symbol="FLAT", date=as_of, avg_volume_10d=900_000, current_price=10, adr_percent=5))
        # Plenty of non-SPY history must still not be used as a substitute
        # session calendar when the SPY series is unavailable.
        db.add_all(
            StockPrice(symbol="FLAT", date=session_date, open=10, high=10, low=10, close=10, volume=1)
            for session_date in dates
        )
        db.add(StockPrice(symbol="FLAT", date=as_of, open=10, high=10, low=10, close=10, volume=1))
        db.commit()
        result = asyncio.run(calculate_breadth_comparisons(AsyncSessionShim(db), as_of))

    assert result["up_from_open_vs_down"]["up_ratio"] is None
    assert result["up_from_open_vs_down"]["eligible_symbols"] == 1
    assert result["up_4pct_vs_down_4pct"]["eligible_symbols"] == 0
    assert result["up_4pct_vs_down_4pct"]["excluded_symbols"] == 1
    assert result["new_session_highs_vs_lows"]["eligible_symbols"] == 0
    assert result["new_session_highs_vs_lows"]["excluded_symbols"] == 1
    assert result["new_session_highs_vs_lows"]["up_ratio"] is None


def test_empty_filtered_universe_returns_zero_coverage():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    StockMetrics.__table__.create(engine)
    StockPrice.__table__.create(engine)
    with Session(engine) as db:
        result = asyncio.run(calculate_breadth_comparisons(AsyncSessionShim(db), date(2026, 10, 20)))

    for key in ("new_session_highs_vs_lows", "up_from_open_vs_down", "up_4pct_vs_down_4pct"):
        assert result[key]["eligible_symbols"] == 0
        assert result[key]["excluded_symbols"] == 0
        assert result[key]["up_ratio"] is None


def test_current_endpoint_serializes_breadth_as_additive_participation_data(monkeypatch):
    as_of = date(2026, 10, 20)
    breadth = {
        "date": as_of.isoformat(),
        "new_session_highs_vs_lows": {
            "up_count": 2, "down_count": 1, "eligible_symbols": 3,
            "excluded_symbols": 1, "up_ratio": 2 / 3,
        },
        "up_from_open_vs_down": {
            "up_count": 0, "down_count": 0, "eligible_symbols": 0,
            "excluded_symbols": 4, "up_ratio": None,
        },
        "up_4pct_vs_down_4pct": {
            "up_count": 0, "down_count": 1, "eligible_symbols": 2,
            "excluded_symbols": 2, "up_ratio": 0,
        },
    }
    ctx = MarketContext(
        as_of=as_of, universe_size=4,
        participation=ParticipationAnalysis("STABLE", 0, 20, {"breadth_above_ema21": 0.5}, breadth),
        leadership=LeadershipAnalysis("HEALTHY", 0, {}), engines_pending=[],
    )

    class FakeEngine:
        def __init__(self, _db):
            pass

        async def analyze(self):
            return ctx

    from app.api.v1.endpoints import market_context as endpoint
    monkeypatch.setattr(endpoint, "MarketContextEngine", FakeEngine)
    async def no_index(_db):
        return None
    monkeypatch.setattr(endpoint, "_build_index_block", no_index)
    payload = asyncio.run(endpoint.get_current_market_context(object()))

    assert payload["participation"]["breadth_comparisons"] == breadth
    assert payload["posture"] is None


def test_previous_session_extremes_need_no_annual_history_and_ignore_older_extremes():
    engine = create_engine("sqlite:///:memory:")
    for model in (Stock, StockMetrics, StockPrice):
        model.__table__.create(engine)
    monday, friday, thursday = date(2026, 10, 19), date(2026, 10, 16), date(2026, 10, 15)
    with Session(engine) as db:
        for symbol in ("NEW", "OLDER"):
            db.add(Stock(symbol=symbol, name=symbol, sector="Technology", market_cap=700_000_000))
            db.add(StockMetrics(symbol=symbol, date=monday, current_price=10,
                                avg_volume_10d=900_000, adr_percent=5))
            for day, high, low in ((friday, 10, 5), (monday, 11, 4)):
                db.add(StockPrice(symbol=symbol, date=day, open=8, high=high, low=low,
                                  close=8, volume=100))
        # This older range would prevent an annual breakout, but is irrelevant now.
        db.add(StockPrice(symbol="OLDER", date=thursday, open=8, high=100, low=1,
                          close=8, volume=100))
        for day in (thursday, friday, monday):
            db.add(StockPrice(symbol="SPY", date=day, open=500, high=501, low=499,
                              close=500, volume=100))
        db.commit()
        result = asyncio.run(calculate_breadth_comparisons(AsyncSessionShim(db), monday))
        assert result["new_session_highs_vs_lows"] == {
            "up_count": 2, "down_count": 2, "eligible_symbols": 2,
            "excluded_symbols": 0, "up_ratio": 0.5,
        }
        assert "new_52w_highs_vs_lows" not in result
    engine.dispose()


def test_session_extreme_rejects_invalid_pairs_and_handles_ties_and_each_side():
    from app.services.market_context_breadth import evaluate_session_extreme

    assert evaluate_session_extreme(10, 5, [(10, 5)]) == (True, False, False)
    assert evaluate_session_extreme(11, 5, [(10, 5)]) == (True, True, False)
    assert evaluate_session_extreme(10, 4, [(10, 5)]) == (True, False, True)
    assert evaluate_session_extreme(11, 4, [(10, 5)]) == (True, True, True)
    for pair in ((None, 5), (0, 5), (10, -1), (inf, 5), (10, float("nan")), (4, 5)):
        assert evaluate_session_extreme(11, 4, [pair]) == (False, False, False)
        assert evaluate_session_extreme(*pair, [(10, 5)]) == (False, False, False)
    assert evaluate_session_extreme(11, 4, []) == (False, False, False)
