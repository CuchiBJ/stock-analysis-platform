import asyncio
import hashlib
import json
import argparse
import sys
import types
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts import recover_qqq


def sample_rows():
    start = date(2024, 1, 2)
    dates = [start + timedelta(days=i) for i in range(260)]
    rows = [{"date": d.isoformat(), "open": 100.0, "high": 102.0,
             "low": 99.0, "close": 101.0, "volume": 1000} for d in dates]
    return dates, rows


def test_candidate_accepts_exact_reference_sessions():
    dates, rows = sample_rows()
    recover_qqq.validate_rows(rows, [d.isoformat() for d in dates], date(2026, 1, 1))


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.pop(),
    lambda rows: rows.__setitem__(1, dict(rows[0])),
    lambda rows: rows[0].update(high=98.0),
    lambda rows: rows[0].update(date="not-a-date"),
    lambda rows: rows[0].update(close=float("nan")),
    lambda rows: rows[0].update(volume=2_147_483_648),
    lambda rows: rows[0].update(symbol="SPY"),
    lambda rows: rows.__setitem__(0, None),
])
def test_candidate_rejects_malformed_rows(mutate):
    dates, rows = sample_rows()
    mutate(rows)
    with pytest.raises(ValueError):
        recover_qqq.validate_rows(rows, [d.isoformat() for d in dates], date(2026, 1, 1))


class _Result:
    def __init__(self, values=()):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None


class _Db:
    def __init__(self, refs, latest_window=None):
        self.refs = refs
        self.latest_window = latest_window or refs
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        sql = str(statement)
        params = statement.compile().params
        expr = statement.column_descriptions[0]["expr"]
        if expr is recover_qqq.StockPrice.date:
            if "SPY" in params.values():
                return _Result(self.refs)
            if "LIMIT" in sql:
                return _Result(self.latest_window)
            return _Result(self.refs)
        if "stock_prices" in sql or "stock_metrics" in sql:
            return _Result(())
        return _Result(self.refs)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1
        self.added.clear()


def test_calculation_fault_rolls_back_all_price_inserts(tmp_path, monkeypatch):
    refs, rows = sample_rows()
    candidate_path = tmp_path / "candidate.json"
    backup_path = tmp_path / "backup.json"
    payload = {"symbol": "QQQ", "source": "yfinance:auto_adjust=True",
               "reference_dates": [d.isoformat() for d in refs], "rows": rows,
               "prepared_at": "2026-10-26T00:00:00+00:00"}
    raw = json.dumps(payload, sort_keys=True).encode()
    candidate_path.write_bytes(raw)
    backup_path.write_text('{"version":1,"symbol":"QQQ","prices":[],"metrics":[]}')

    class FailingCalculator:
        def __init__(self, db):
            pass

        async def calculate_metrics_for_symbol(self, *args, **kwargs):
            raise RuntimeError("injected metrics failure")

    monkeypatch.setattr("app.data.ingestors.metrics_calculator.MetricsCalculator", FailingCalculator)
    db = _Db(refs)
    with pytest.raises(RuntimeError, match="injected metrics failure"):
        asyncio.run(recover_qqq.execute(db, candidate_path, backup_path, hashlib.sha256(raw).hexdigest()))
    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.added == []


def test_existing_extra_qqq_session_rolls_back(tmp_path, monkeypatch):
    refs, rows = sample_rows()
    candidate_path = tmp_path / "candidate.json"
    backup_path = tmp_path / "backup.json"
    payload = {"symbol": "QQQ", "source": "yfinance:auto_adjust=True",
               "reference_dates": [d.isoformat() for d in refs], "rows": rows,
               "prepared_at": "2026-10-26T00:00:00+00:00"}
    raw = json.dumps(payload, sort_keys=True).encode()
    candidate_path.write_bytes(raw)
    backup_path.write_text('{"version":1,"symbol":"QQQ","prices":[],"metrics":[]}')

    class GoodMetrics:
        def __init__(self):
            self.symbol = "QQQ"
            self.date = refs[-1]
            self.current_price = self.ema50 = self.ema200 = self.sma150 = self.sma200 = self.high_52w = 101.0

    class Calculator:
        def __init__(self, db):
            pass

        async def calculate_metrics_for_symbol(self, *args, **kwargs):
            return GoodMetrics()

    monkeypatch.setattr("app.data.ingestors.metrics_calculator.MetricsCalculator", Calculator)
    latest_window = refs[1:] + [refs[-1] + timedelta(days=1)]
    db = _Db(refs, latest_window=latest_window)
    with pytest.raises(ValueError, match="latest 260 QQQ"):
        asyncio.run(recover_qqq.execute(db, candidate_path, backup_path, hashlib.sha256(raw).hexdigest()))
    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.added == []


def test_prepare_filters_extra_provider_sessions(monkeypatch, tmp_path):
    pd = pytest.importorskip("pandas")
    refs, _ = sample_rows()
    index = [refs[0] - timedelta(days=1)] + refs + [refs[-1] + timedelta(days=1)]
    frame = pd.DataFrame({"Open": [100.0] * len(index), "High": [102.0] * len(index),
                          "Low": [99.0] * len(index), "Close": [101.0] * len(index),
                          "Volume": [1000] * len(index)}, index=pd.to_datetime(index))
    calls = {}
    monkeypatch.setattr(recover_qqq, "reference_dates", lambda db: _async_result(refs))
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=lambda *a, **kw: _capture(calls, frame, a, kw)))
    path = tmp_path / "candidate.json"
    result = asyncio.run(recover_qqq.prepare(object(), path))
    assert len(result["rows"]) == 260
    assert [row["date"] for row in result["rows"]] == [d.isoformat() for d in refs]
    assert calls["args"][0] == "QQQ"
    assert calls["kwargs"]["auto_adjust"] is True
    assert calls["kwargs"]["threads"] is False
    assert json.loads(path.read_text())["source"] == "yfinance:auto_adjust=True"


async def _async_result(value):
    return value


def _capture(calls, frame, args, kwargs):
    calls["args"] = args
    calls["kwargs"] = kwargs
    return frame


def test_cli_prepare_reports_candidate_row_count(monkeypatch, capsys, tmp_path):
    refs, rows = sample_rows()
    payload = {"rows": rows, "reference_dates": [d.isoformat() for d in refs]}

    class Engine:
        async def dispose(self):
            pass

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(recover_qqq, "create_async_engine", lambda *a, **kw: Engine())
    monkeypatch.setattr(recover_qqq, "async_sessionmaker", lambda *a, **kw: lambda: SessionContext())
    async def fake_prepare(db, path):
        return payload
    monkeypatch.setattr(recover_qqq, "prepare", fake_prepare)
    args = argparse.Namespace(execute=False, candidate=str(tmp_path / "candidate.json"), backup=None, sha256=None)
    asyncio.run(recover_qqq.run(args))
    assert json.loads(capsys.readouterr().out)["price_count"] == 260


class _CalculatorDb:
    def __init__(self, refs):
        self.refs = refs
        self.prices = []
        self.metrics = []
        self.pending = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        description = statement.column_descriptions[0]
        entity, expr = description["entity"], description["expr"]
        params = statement.compile().params
        if expr is recover_qqq.StockPrice.date:
            if "SPY" in params.values():
                return _Result(self.refs)
            price_rows = [p for p in self.prices + self.pending if isinstance(p, recover_qqq.StockPrice)]
            return _Result(sorted((p.date for p in price_rows), reverse=True)[:260])
        if entity is recover_qqq.StockPrice:
            dates = [v for v in params.values() if isinstance(v, date)]
            if dates and statement._limit_clause is None:
                return _Result([p for p in self.prices + self.pending if p.date == dates[0]])
            ordered = sorted(self.prices + self.pending, key=lambda p: p.date, reverse=statement._limit_clause is not None)
            return _Result(ordered[:260] if statement._limit_clause is not None else ordered)
        return _Result([])

    def add(self, item):
        self.pending.append(item)

    async def flush(self):
        pass

    async def commit(self):
        self.prices.extend(x for x in self.pending if isinstance(x, recover_qqq.StockPrice))
        self.metrics.extend(x for x in self.pending if isinstance(x, recover_qqq.StockMetrics))
        self.pending.clear()
        self.commits += 1

    async def rollback(self):
        self.pending.clear()
        self.rollbacks += 1


def test_execute_with_real_metrics_calculator_offline(tmp_path):
    refs, rows = sample_rows()
    for index, row in enumerate(rows):
        close = 50.0 + index * 0.25
        row.update(open=close - 0.1, high=close + 1.0, low=close - 1.0, close=close, volume=100_000 + index)
    payload = {"symbol": "QQQ", "source": "yfinance:auto_adjust=True",
               "reference_dates": [d.isoformat() for d in refs], "rows": rows,
               "prepared_at": "2026-10-26T00:00:00+00:00"}
    candidate_path = tmp_path / "candidate.json"
    backup_path = tmp_path / "backup.json"
    raw = json.dumps(payload, sort_keys=True).encode()
    candidate_path.write_bytes(raw)
    backup_path.write_text('{"version":1,"symbol":"QQQ","prices":[],"metrics":[]}')
    db = _CalculatorDb(refs)
    result = asyncio.run(recover_qqq.execute(db, candidate_path, backup_path, hashlib.sha256(raw).hexdigest()))
    assert result == {"prices_upserted": 260, "metrics_written": 1, "latest_date": refs[-1].isoformat()}
    assert db.commits == 1
    assert len(db.prices) == 260
    assert len(db.metrics) == 1
    assert db.metrics[0].high_52w == max(row["close"] for row in rows[-252:])


class _SqliteAsyncShim:
    """Async-shaped adapter over a real in-memory SQLite SQLAlchemy session."""
    def __init__(self, session):
        self.session = session
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, item):
        self.session.add(item)

    async def flush(self):
        self.session.flush()
        self.flushes += 1

    async def commit(self):
        self.session.commit()
        self.commits += 1

    async def rollback(self):
        self.session.rollback()
        self.rollbacks += 1


def _sqlite_case(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    recover_qqq.StockPrice.__table__.create(engine)
    recover_qqq.StockMetrics.__table__.create(engine)
    refs, rows = sample_rows()
    with Session(engine) as seed:
        for index, d in enumerate(refs):
            close = 50.0 + index * 0.25
            seed.add(recover_qqq.StockPrice(symbol="SPY", date=d, open=close - .1, high=close + 1,
                                           low=close - 1, close=close, volume=100_000 + index))
        # An existing QQQ bar and latest metric prove updates are rolled back/restored too.
        seed.add(recover_qqq.StockPrice(symbol="QQQ", date=refs[0], open=7, high=8, low=6,
                                       close=7, volume=70))
        seed.add(recover_qqq.StockMetrics(symbol="QQQ", date=refs[-1], current_price=7,
                                         ema50=7, ema200=7, sma150=7, sma200=7, high_52w=7))
        seed.add(recover_qqq.StockPrice(symbol="IWM", date=refs[-1], open=31, high=32, low=30,
                                       close=31, volume=310))
        seed.add(recover_qqq.StockMetrics(symbol="IWM", date=refs[-1], current_price=31,
                                         ema50=30, ema200=29, sma150=28, sma200=27, high_52w=32))
        seed.commit()

    for index, row in enumerate(rows):
        close = 50.0 + index * 0.25
        row.update(open=close - .1, high=close + 1.0, low=close - 1.0, close=close, volume=100_000 + index)
    payload = {"symbol": "QQQ", "source": "yfinance:auto_adjust=True",
               "reference_dates": [d.isoformat() for d in refs], "rows": rows,
               "prepared_at": "2026-10-26T00:00:00+00:00"}
    candidate_path = tmp_path / "candidate.json"
    backup_path = tmp_path / "backup.json"
    raw = json.dumps(payload, sort_keys=True).encode()
    candidate_path.write_bytes(raw)
    session = Session(engine)
    db = _SqliteAsyncShim(session)
    backup = asyncio.run(recover_qqq.read_qqq_snapshot(db))
    recover_qqq.write_json(backup_path, backup)
    session.rollback()
    db.commits = db.rollbacks = db.flushes = 0
    return engine, session, db, refs, rows, candidate_path, backup_path, raw


def test_sqlite_execute_commits_metrics_and_preserves_other_symbol(tmp_path):
    engine, session, db, refs, rows, candidate_path, backup_path, raw = _sqlite_case(tmp_path)
    try:
        result = asyncio.run(recover_qqq.execute(db, candidate_path, backup_path, hashlib.sha256(raw).hexdigest()))
        assert result["prices_upserted"] == 260
        assert db.commits == 1
        prices = session.execute(select(recover_qqq.StockPrice).where(recover_qqq.StockPrice.symbol == "QQQ")).scalars().all()
        assert len(prices) == 260
        assert next(p for p in prices if p.date == refs[0]).close == rows[0]["close"]
        qqq_metric = session.execute(select(recover_qqq.StockMetrics).where(recover_qqq.StockMetrics.symbol == "QQQ")).scalar_one()
        assert qqq_metric.current_price == rows[-1]["close"]
        assert qqq_metric.high_52w == max(r["close"] for r in rows[-252:])
        iwm_price = session.execute(select(recover_qqq.StockPrice).where(recover_qqq.StockPrice.symbol == "IWM")).scalar_one()
        iwm_metric = session.execute(select(recover_qqq.StockMetrics).where(recover_qqq.StockMetrics.symbol == "IWM")).scalar_one()
        assert (iwm_price.close, iwm_metric.current_price) == (31, 31)
    finally:
        session.close()
        engine.dispose()


def test_sqlite_failure_after_calculator_flush_rolls_back_everything(tmp_path, monkeypatch):
    engine, session, db, refs, _rows, candidate_path, backup_path, raw = _sqlite_case(tmp_path)
    original_calculate = __import__("app.data.ingestors.metrics_calculator", fromlist=["MetricsCalculator"]).MetricsCalculator.calculate_metrics_for_symbol

    async def fail_after_internal_flush(self, *args, **kwargs):
        await original_calculate(self, *args, **kwargs)
        assert db.flushes >= 1
        raise RuntimeError("injected failure after calculator flush")

    monkeypatch.setattr("app.data.ingestors.metrics_calculator.MetricsCalculator.calculate_metrics_for_symbol",
                        fail_after_internal_flush)
    try:
        with pytest.raises(RuntimeError, match="injected failure after calculator flush"):
            asyncio.run(recover_qqq.execute(db, candidate_path, backup_path, hashlib.sha256(raw).hexdigest()))
        assert db.commits == 0
        assert db.rollbacks == 1
        session.expire_all()
        qqq_prices = session.execute(select(recover_qqq.StockPrice).where(recover_qqq.StockPrice.symbol == "QQQ")).scalars().all()
        assert len(qqq_prices) == 1
        assert (qqq_prices[0].date, qqq_prices[0].close) == (refs[0], 7)
        qqq_metric = session.execute(select(recover_qqq.StockMetrics).where(recover_qqq.StockMetrics.symbol == "QQQ")).scalar_one()
        assert (qqq_metric.current_price, qqq_metric.high_52w) == (7, 7)
        iwm_price = session.execute(select(recover_qqq.StockPrice).where(recover_qqq.StockPrice.symbol == "IWM")).scalar_one()
        assert iwm_price.close == 31
    finally:
        session.close()
        engine.dispose()
