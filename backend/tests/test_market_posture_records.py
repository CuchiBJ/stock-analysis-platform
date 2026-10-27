import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.market_posture_record import MarketPostureRecord
from app.services.market_posture_record_service import MarketPostureRecordService


class SyncSessionShim:
    def __init__(self, session):
        self.session = session

    def get_bind(self):
        return self.session.get_bind()

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    MarketPostureRecord.__table__.create(engine)
    with Session(engine) as session:
        yield SyncSessionShim(session), session
    engine.dispose()


def test_upsert_is_per_session_and_rejects_older_observation(db):
    shim, session = db
    service = MarketPostureRecordService()
    day = date(2026, 10, 23)
    first = datetime(2026, 10, 23, 14, tzinfo=timezone.utc)
    later = first + timedelta(hours=1)
    posture = {"state": "NORMAL", "instruction": "Stay selective", "reasons": ["broad"]}
    # Pin repository timestamps to model out-of-order concurrent writes.
    from app.repositories.market_posture_record_repository import MarketPostureRecordRepository
    repo = MarketPostureRecordRepository()
    asyncio.run(repo.upsert(shim, day, "NORMAL", posture, first))
    asyncio.run(repo.upsert(shim, day, "SELECTIVO", {"instruction": "latest"}, later))
    asyncio.run(repo.upsert(shim, day, "AGRESIVO", {"instruction": "stale"}, first))
    other_day = day + timedelta(days=1)
    asyncio.run(repo.upsert(shim, other_day, "DEFENSIVO", {"instruction": "new session"}, later))
    asyncio.run(shim.commit())
    rows = session.execute(select(MarketPostureRecord)).scalars().all()
    assert len(rows) == 2
    by_date = {row.session_date: row for row in rows}
    assert by_date[day].state == "SELECTIVO"
    assert by_date[day].payload == {"instruction": "latest"}
    assert by_date[day].updated_at.replace(tzinfo=timezone.utc) == later
    assert by_date[other_day].state == "DEFENSIVO"


def test_invalid_or_missing_posture_is_not_recorded(db):
    shim, session = db
    service = MarketPostureRecordService()
    assert asyncio.run(service.observe(shim, date(2026, 10, 23), None)) is False
    assert asyncio.run(service.observe(shim, date(2026, 10, 23), {"state": "UNKNOWN"})) is False
    assert session.execute(select(MarketPostureRecord)).scalars().all() == []


def test_sqlalchemy_failure_rolls_back_and_returns_unavailable(db):
    shim, _ = db

    class BrokenRepository:
        async def upsert(self, *args):
            raise SQLAlchemyError("database unavailable")

        async def get_dates(self, *args):
            raise SQLAlchemyError("database unavailable")

    service = MarketPostureRecordService(BrokenRepository())
    assert asyncio.run(service.observe(shim, date(2026, 10, 23), {"state": "NORMAL"})) is False
    assert asyncio.run(service.history(shim, [date(2026, 10, 23)])) == {
        "status": "unavailable", "records": []}


def test_history_returns_only_requested_actual_records(db):
    shim, _ = db
    service = MarketPostureRecordService()
    day = date(2026, 10, 23)
    asyncio.run(service.observe(shim, day, {"state": "NORMAL", "instruction": "hold"}))
    history = asyncio.run(service.history(shim, [day, day - timedelta(days=1)]))
    assert history["status"] == "available"
    assert len(history["records"]) == 1
    assert history["records"][0]["date"] == day.isoformat()
    assert history["records"][0]["instruction"] == "hold"
    assert history["records"][0]["recorded_at"].endswith("+00:00")


def test_observation_persists_complete_emitted_payload(db):
    shim, session = db
    posture = {
        "state": "DEFENSIVO", "instruction": "Reduce exposure",
        "reasons": ["breadth deteriorated"], "unlock": ["breadth repairs"],
        "policy": {"version": 2, "current_damage": "confirmed"},
    }
    assert asyncio.run(MarketPostureRecordService().observe(
        shim, date(2026, 10, 23), posture
    )) is True
    stored = session.execute(select(MarketPostureRecord)).scalar_one()
    assert stored.payload == posture


def test_missing_table_read_and_write_failures_are_contained():
    engine = create_engine("sqlite:///:memory:")
    try:
        with Session(engine) as session:
            shim = SyncSessionShim(session)
            service = MarketPostureRecordService()
            assert asyncio.run(service.observe(
                shim, date(2026, 10, 23), {"state": "NORMAL"}
            )) is False
            assert asyncio.run(service.history(shim, [date(2026, 10, 23)])) == {
                "status": "unavailable", "records": []
            }
    finally:
        engine.dispose()
