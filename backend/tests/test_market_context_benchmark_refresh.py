"""Offline regressions for Market Context benchmark price ingestion."""
import asyncio
from contextlib import asynccontextmanager
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import Insert as PostgreSQLInsert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
import pytest

from app.data import scheduler as scheduler_module
from app.data.ingestors.polygon_eod_ingestor import PolygonEODIngestor
from app.data.scheduler import DataScheduler
from app.models.stock import Stock, StockPrice
from app.services.sector_etf_momentum import SECTOR_ETFS
from tests.test_market_context_breadth import AsyncSessionShim


@pytest.mark.parametrize("active_symbols", [[], ["AAA", "SPY", "QQQ", "AAA"]])
def test_scheduled_price_download_includes_market_context_references(monkeypatch, active_symbols):
    scheduler = DataScheduler()
    original_symbols = list(active_symbols)

    class ActiveUniverse:
        def __init__(self, db):
            pass

        async def get_active_symbols(self, limit=None):
            return active_symbols

    @asynccontextmanager
    async def empty_db():
        yield object()

    captured = []
    monkeypatch.setattr(scheduler_module, "StockIngestor", ActiveUniverse)
    monkeypatch.setattr(scheduler, "_get_db", empty_db)
    monkeypatch.setattr(scheduler, "_bulk_download_prices_sync", lambda symbols: captured.extend(symbols))

    asyncio.run(scheduler._update_prices())

    assert captured == list(dict.fromkeys([*original_symbols, "SPY", "QQQ", *SECTOR_ETFS]))
    assert active_symbols == original_symbols
    assert captured.count("SPY") == 1
    assert captured.count("QQQ") == 1
    assert all(captured.count(symbol) == 1 for symbol in ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK",
                                                           "XLP", "XLRE", "XLU", "XLV", "XLY"))


def test_polygon_eod_persists_qqq_without_stocks_membership_and_filters_other_symbols():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    StockPrice.__table__.create(engine)

    class PostgreSQLInsertSQLiteShim:
        def __init__(self, session):
            self.session = session

        async def execute(self, statement):
            if isinstance(statement, PostgreSQLInsert):
                values = statement._multi_values[0]
                sqlite_stmt = sqlite_insert(StockPrice).values(values).on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_={key: getattr(sqlite_insert(StockPrice).excluded, key)
                          for key in ("open", "high", "low", "close", "volume")},
                )
                return self.session.execute(sqlite_stmt)
            return self.session.execute(statement)

        async def commit(self):
            self.session.commit()

    close = [504]

    async def check(session):
        ingestor = PolygonEODIngestor(PostgreSQLInsertSQLiteShim(session))

        async def fake_bars(_target_date):
            return [
                {"symbol": "QQQ", "date": date(2026, 10, 23), "open": 500,
                 "high": 505, "low": 499, "close": close[0], "volume": 1000},
                {"symbol": "UNRELATED", "date": date(2026, 10, 23), "open": 10,
                 "high": 11, "low": 9, "close": 10, "volume": 100},
            ]

        ingestor.fetch_grouped_daily_bars = fake_bars
        stats = await ingestor.ingest_eod(date(2026, 10, 23))
        return stats

    try:
        with Session(engine) as db:
            stats = asyncio.run(check(db))
            assert stats["written"] == 1
            assert db.query(StockPrice.symbol).all() == [("QQQ",)]
            close[0] = 503
            asyncio.run(check(db))
            assert db.query(StockPrice).one().close == 503
    finally:
        engine.dispose()


def test_slow_selection_includes_qqq_price_without_stock_membership():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    StockPrice.__table__.create(engine)
    day = date(2026, 10, 23)
    try:
        with Session(engine) as db:
            db.add(StockPrice(symbol="QQQ", date=day, open=500, high=505,
                              low=499, close=504, volume=1000))
            db.commit()
            symbols, as_of = asyncio.run(DataScheduler()._get_slow_symbols_and_date(AsyncSessionShim(db)))
            assert symbols == ["QQQ"]
            assert as_of == day
            assert db.query(Stock).filter_by(symbol="QQQ").count() == 0
    finally:
        engine.dispose()
