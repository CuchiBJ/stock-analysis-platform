"""Offline evidence for session capture and scheduler recovery without HTTP visits."""
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.data import scheduler as scheduler_module
from app.data.post_close_cycle import NEW_YORK, PostCloseCycle, SlowMetricsRun
from app.data.scheduler import DataScheduler
from app.models.market_posture_record import MarketPostureRecord
from app.models.stock import StockMetrics
from app.services import market_context_engine, market_posture_capture
from app.services.market_context_engine import MarketContextEngine
from app.services.market_posture import Posture
from app.services.market_posture_record_service import MarketPostureRecordService
from tests.test_market_posture_records import SyncSessionShim

DAY = date(2026, 10, 26)
NOW = datetime(2026, 10, 26, 16, 10, tzinfo=NEW_YORK)


def context(**overrides):
    values = dict(as_of=DAY, universe_size=20,
                  posture=Posture("SELECTIVO", "Evaluate selectively", ["repair pending"],
                                  "confirmed repair", {"version": 2}))
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    MarketPostureRecord.__table__.create(engine)
    StockMetrics.__table__.create(engine)
    with Session(engine) as session:
        yield SyncSessionShim(session), session
    engine.dispose()


def scheduler_for(db, metrics=None):
    shim, _ = db

    @asynccontextmanager
    async def get_db():
        yield shim

    return SimpleNamespace(
        _get_db=get_db, _update_prices_polygon_eod=AsyncMock(),
        _trigger_metrics_run=AsyncMock(return_value=metrics or SlowMetricsRun(19, 20, DAY)),
        _record_heartbeat=AsyncMock(), _slow_last_attempted=99999,
    )


def stub_context(monkeypatch, value):
    analyze = AsyncMock(return_value=value)
    monkeypatch.setattr(market_posture_capture, "MarketContextEngine", lambda db: SimpleNamespace(analyze=analyze))
    return analyze


def records(db):
    return db[1].execute(select(MarketPostureRecord)).scalars().all()


def test_no_visits_capture_awaits_prices_metrics_and_persistence(db, monkeypatch):
    scheduler = scheduler_for(db)
    steps = []

    async def prices(day):
        assert day == DAY
        steps.append("prices")

    async def metrics(*, refresh):
        assert refresh
        assert steps == ["prices"]
        steps.append("metrics committed")
        return SlowMetricsRun(19, 20, DAY)

    async def analyze(*, use_cache):
        assert use_cache is False
        assert steps == ["prices", "metrics committed"]
        steps.append("posture")
        return context()

    scheduler._update_prices_polygon_eod = prices
    scheduler._trigger_metrics_run = metrics
    monkeypatch.setattr(market_posture_capture, "MarketContextEngine", lambda db: SimpleNamespace(analyze=analyze))
    result = asyncio.run(PostCloseCycle(lambda: NOW).run_if_due(scheduler))
    assert result.success
    row, = records(db)
    assert row.session_date == DAY
    assert row.payload == dict(state="SELECTIVO", instruction="Evaluate selectively",
                              reasons=["repair pending"], unlock="confirmed repair", policy={"version": 2})
    assert row.recorded_at.date() == datetime.now(timezone.utc).date()
    heartbeat = scheduler._record_heartbeat.call_args.kwargs
    assert heartbeat["status"] == "ok"
    assert (heartbeat["symbols_processed"], heartbeat["symbols_expected"]) == (19, 20)


@pytest.mark.parametrize("run,error", [
    (SlowMetricsRun(skipped=True), "another run"),
    (SlowMetricsRun(0, 20, DAY), "no symbols"),
    (SlowMetricsRun(0, 0, DAY), "no symbols"),
    (SlowMetricsRun(18, 20, DAY), "95%"),
    (SlowMetricsRun(20, 20, DAY - timedelta(days=1)), "snapshot"),
    (SlowMetricsRun(20, 20, DAY + timedelta(days=1)), "snapshot"),
])
def test_unqualified_slow_cannot_use_stale_shared_counters(db, monkeypatch, run, error):
    scheduler = scheduler_for(db, run)
    analyze = stub_context(monkeypatch, context())
    cycle = PostCloseCycle(lambda: NOW)
    result = asyncio.run(cycle.run_if_due(scheduler))
    assert not result.success and error in result.error
    assert cycle.completed_date is None
    assert records(db) == []
    analyze.assert_not_awaited()
    assert scheduler._record_heartbeat.call_args.kwargs["status"] == "failed"
    assert error in scheduler._record_heartbeat.call_args.kwargs["error_message"]


@pytest.mark.parametrize("ctx", [
    None, context(as_of=DAY - timedelta(days=1)), context(as_of=DAY + timedelta(days=1)),
    context(as_of=datetime(2026, 10, 26)), context(universe_size=0), context(posture=None),
    context(posture=Posture("UNKNOWN", "invalid")),
    context(posture=Posture("NORMAL", "")),
    context(posture=Posture("NORMAL", "hold", reasons=None)),
    context(posture=Posture("NORMAL", "hold", policy=None)),
])
def test_invalid_current_context_never_manufactures_record(db, monkeypatch, ctx):
    stub_context(monkeypatch, ctx)
    result = asyncio.run(PostCloseCycle(lambda: NOW).run_if_due(scheduler_for(db)))
    assert not result.success
    assert records(db) == []


def test_capture_retries_after_300_seconds_from_failure_completion(db, monkeypatch):
    now = [NOW]
    analyze = stub_context(monkeypatch, context())
    analyze.side_effect = [RuntimeError("private details must not enter heartbeat"), context()]
    scheduler = scheduler_for(db)
    cycle = PostCloseCycle(lambda: now[0])
    first = asyncio.run(cycle.run_if_due(scheduler))
    assert first.error == "RuntimeError"
    now[0] += timedelta(seconds=299)
    assert asyncio.run(cycle.run_if_due(scheduler)) is None
    now[0] += timedelta(seconds=1)
    assert asyncio.run(cycle.run_if_due(scheduler)).success
    now[0] += timedelta(hours=1)
    assert asyncio.run(cycle.run_if_due(scheduler)) is None
    assert scheduler._update_prices_polygon_eod.await_count == 2
    assert len(records(db)) == 1


def test_slow_attempt_time_does_not_shorten_retry_delay(db, monkeypatch):
    now = [NOW]
    scheduler = scheduler_for(db)

    async def slow_failure(*, refresh):
        now[0] += timedelta(minutes=20)
        raise RuntimeError("failure")

    scheduler._trigger_metrics_run = slow_failure
    cycle = PostCloseCycle(lambda: now[0])
    assert not asyncio.run(cycle.run_if_due(scheduler)).success
    now[0] += timedelta(seconds=299)
    assert asyncio.run(cycle.run_if_due(scheduler)) is None


@pytest.mark.parametrize("when", [
    NOW.replace(hour=16, minute=9), NOW.replace(hour=9),
    NOW.replace(day=24), NOW.replace(day=25), NOW.replace(day=27, hour=0),
])
def test_no_capture_outside_existing_weekday_window(db, when):
    scheduler = scheduler_for(db)
    assert asyncio.run(PostCloseCycle(lambda: when).run_if_due(scheduler)) is None
    scheduler._update_prices_polygon_eod.assert_not_awaited()


def test_midnight_during_calculation_rejects_backfill_and_preserves_target(db, monkeypatch):
    now = [NOW.replace(hour=23, minute=59)]
    scheduler = scheduler_for(db)

    async def analyze(*, use_cache):
        now[0] += timedelta(minutes=2)
        return context()

    monkeypatch.setattr(market_posture_capture, "MarketContextEngine", lambda db: SimpleNamespace(analyze=analyze))
    cycle = PostCloseCycle(lambda: now[0])
    result = asyncio.run(cycle.run_if_due(scheduler))
    assert result.target == DAY and not result.success
    assert "session ended" in result.error
    scheduler._update_prices_polygon_eod.assert_awaited_once_with(DAY)
    assert records(db) == []
    assert asyncio.run(cycle.run_if_due(scheduler)) is None


def test_restart_recapture_and_request_observation_keep_one_latest_row(db, monkeypatch):
    stub_context(monkeypatch, context())
    scheduler = scheduler_for(db)
    for _ in range(2):
        assert asyncio.run(PostCloseCycle(lambda: NOW).run_if_due(scheduler)).success
    assert len(records(db)) == 1
    service = MarketPostureRecordService()
    assert asyncio.run(service.observe(db[0], DAY, {"state": "NORMAL", "instruction": "latest visit"}))
    db[1].expire_all()
    row, = records(db)
    assert row.state == "NORMAL" and row.payload["instruction"] == "latest visit"


def test_persistence_failure_keeps_committed_metrics_and_failed_heartbeat(db, monkeypatch):
    stub_context(monkeypatch, context())
    db[1].add(StockMetrics(symbol="AAA", date=DAY))
    db[1].commit()

    class BrokenRepository:
        async def upsert(self, *args):
            raise SQLAlchemyError("not available")

    monkeypatch.setattr(market_posture_capture, "market_posture_record_service", MarketPostureRecordService(BrokenRepository()))
    scheduler = scheduler_for(db)
    cycle = PostCloseCycle(lambda: NOW)
    assert not asyncio.run(cycle.run_if_due(scheduler)).success
    assert cycle.completed_date is None
    assert db[1].execute(select(StockMetrics)).scalar_one().symbol == "AAA"
    assert scheduler._record_heartbeat.call_args.kwargs["status"] == "failed"
    assert records(db) == []


def test_coordinator_overlap_does_not_launch_another_cycle(db, monkeypatch):
    scheduler = scheduler_for(db)
    stub_context(monkeypatch, context())
    cycle = PostCloseCycle(lambda: NOW)

    async def check():
        started, release = asyncio.Event(), asyncio.Event()

        async def wait_prices(target):
            started.set()
            await release.wait()

        scheduler._update_prices_polygon_eod = wait_prices
        running = asyncio.create_task(cycle.run_if_due(scheduler))
        await started.wait()
        assert await cycle.run_if_due(scheduler) is None
        release.set()
        assert (await running).success

    asyncio.run(check())
    assert len(records(db)) == 1


def slow_scheduler_for(db, monkeypatch):
    scheduler = DataScheduler()
    scheduler._get_db = scheduler_for(db)._get_db
    scheduler._get_slow_symbols_and_date = AsyncMock(return_value=(["AAA"], DAY))
    scheduler._broadcast_metrics_updated = AsyncMock()
    scheduler._evaluate_pending_outcomes = AsyncMock()
    scheduler._batch_scan_transitions = AsyncMock()
    return scheduler


def test_uncached_current_analysis_ignores_live_cache(monkeypatch):
    engine = MarketContextEngine(None)
    engine._latest_date = AsyncMock(return_value=DAY)
    stale = context()
    MarketContextEngine.clear_cache()
    market_context_engine._cache[DAY] = (stale, datetime.utcnow())
    engine._universe_size = AsyncMock(side_effect=RuntimeError("fresh database read"))
    try:
        assert asyncio.run(engine.analyze()) is stale
        with pytest.raises(RuntimeError, match="fresh database read"):
            asyncio.run(engine.analyze(use_cache=False))
    finally:
        MarketContextEngine.clear_cache()


@pytest.mark.parametrize("metric_offset", [None, -1, 1, 0])
def test_slow_coverage_counts_only_actual_same_snapshot_metrics(db, monkeypatch, metric_offset):
    scheduler = slow_scheduler_for(db, monkeypatch)
    scheduler._slow_last_attempted = 2000
    returned = None if metric_offset is None else SimpleNamespace(date=DAY + timedelta(days=metric_offset))
    calculate = AsyncMock(return_value=returned)
    monkeypatch.setattr(scheduler_module, "MetricsCalculator", lambda db: SimpleNamespace(calculate_metrics_for_symbol=calculate))
    run = asyncio.run(scheduler._trigger_metrics_run())
    assert run == SlowMetricsRun(int(metric_offset == 0), 1, DAY)


def test_future_fresh_metric_does_not_skip_current_snapshot_calculation(db, monkeypatch):
    db[1].add(StockMetrics(symbol="AAA", date=DAY + timedelta(days=1), updated_at=datetime.utcnow()))
    db[1].commit()
    scheduler = slow_scheduler_for(db, monkeypatch)
    calculate = AsyncMock(return_value=None)
    monkeypatch.setattr(scheduler_module, "MetricsCalculator", lambda db: SimpleNamespace(calculate_metrics_for_symbol=calculate))
    run = asyncio.run(scheduler._trigger_metrics_run())
    calculate.assert_awaited_once_with("AAA")
    assert run.covered == 0


def test_overlapping_slow_has_explicit_result_and_preserves_public_integer_contract():
    scheduler = DataScheduler()
    scheduler._slow_running = True
    scheduler._slow_last_attempted = 2000
    assert asyncio.run(scheduler._trigger_metrics_run()) == SlowMetricsRun(skipped=True)
    assert asyncio.run(scheduler.trigger_metrics_update()) == 0


@pytest.mark.parametrize("refresh", [False, True])
def test_post_close_refresh_cannot_reuse_pre_eod_recent_metrics(db, monkeypatch, refresh):
    db[1].add(StockMetrics(symbol="AAA", date=DAY, updated_at=datetime.utcnow()))
    db[1].commit()
    scheduler = slow_scheduler_for(db, monkeypatch)
    calculate = AsyncMock(return_value=None)
    monkeypatch.setattr(scheduler_module, "MetricsCalculator", lambda db: SimpleNamespace(calculate_metrics_for_symbol=calculate))
    run = asyncio.run(scheduler._trigger_metrics_run(refresh=refresh))
    if refresh:
        calculate.assert_awaited_once_with("AAA")
        assert run.covered == 0
    else:
        calculate.assert_not_awaited()
        assert run.covered == 1


@pytest.mark.parametrize("fail_prices", [False, True])
def test_scheduler_loop_wires_capture_and_continues_other_jobs(db, monkeypatch, fail_prices):
    """One real loop iteration proves integration and isolation without HTTP or live feeds."""
    fake = scheduler_for(db)
    scheduler = DataScheduler()
    scheduler._running = True
    scheduler._get_db = fake._get_db
    scheduler._post_close_cycle = PostCloseCycle(lambda: NOW)
    scheduler._record_heartbeat = fake._record_heartbeat
    scheduler._trigger_metrics_run = fake._trigger_metrics_run
    scheduler._update_prices_polygon_eod = fake._update_prices_polygon_eod
    if fail_prices:
        scheduler._update_prices_polygon_eod.side_effect = RuntimeError("feed failed")
    scheduler.universe_engine.tier_manager.load_tiers_from_database = AsyncMock()
    for method in ("_update_prices", "trigger_metrics_update", "trigger_quality_refresh",
                   "_run_discovery_scans", "_reevaluate_tiers", "_run_lifecycle_tracking"):
        monkeypatch.setattr(scheduler, method, AsyncMock())
    scheduler._run_health_check = AsyncMock(return_value=None)
    stub_context(monkeypatch, context())

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)

    async def stop_loop(seconds):
        scheduler._running = False

    monkeypatch.setattr(scheduler_module, "datetime", FixedDateTime)
    monkeypatch.setattr(scheduler_module.asyncio, "sleep", stop_loop)
    asyncio.run(scheduler._scheduler_loop())
    scheduler._run_discovery_scans.assert_awaited_once()
    scheduler._reevaluate_tiers.assert_awaited_once()
    scheduler._run_lifecycle_tracking.assert_awaited_once()
    assert len(records(db)) == (0 if fail_prices else 1)
    heartbeat = scheduler._record_heartbeat.call_args.kwargs
    assert heartbeat["status"] == ("failed" if fail_prices else "ok")
    if fail_prices:
        assert scheduler._post_close_cycle.completed_date is None
        scheduler._trigger_metrics_run.assert_not_awaited()


def test_next_session_targets_today_without_historical_catchup(db, monkeypatch):
    now = [NOW]
    current = [context()]
    analyze = AsyncMock(side_effect=lambda **kwargs: current[0])
    monkeypatch.setattr(market_posture_capture, "MarketContextEngine", lambda db: SimpleNamespace(analyze=analyze))
    scheduler = scheduler_for(db)
    cycle = PostCloseCycle(lambda: now[0])
    assert asyncio.run(cycle.run_if_due(scheduler)).success
    now[0] += timedelta(days=2)
    target = DAY + timedelta(days=2)
    current[0] = context(as_of=target)
    scheduler._trigger_metrics_run.return_value = SlowMetricsRun(20, 20, target)
    assert asyncio.run(cycle.run_if_due(scheduler)).success
    assert {row.session_date for row in records(db)} == {DAY, target}
    assert [call.args[0] for call in scheduler._update_prices_polygon_eod.call_args_list] == [DAY, target]
