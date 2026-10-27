from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market_posture_record_repository import MarketPostureRecordRepository

logger = logging.getLogger(__name__)
KNOWN_STATES = {"FUERA", "DEFENSIVO", "SELECTIVO", "NORMAL", "AGRESIVO"}


def serialize_posture(posture) -> dict | None:
    """Keep request and scheduled observations on the same emitted contract."""
    if posture is None:
        return None
    return {
        "state": posture.state,
        "instruction": posture.instruction,
        "reasons": posture.reasons,
        "unlock": posture.unlock,
        "policy": posture.policy,
    }


class MarketPostureRecordService:
    def __init__(self, repository: MarketPostureRecordRepository | None = None):
        self.repository = repository or MarketPostureRecordRepository()

    @staticmethod
    def valid_date(value) -> date | None:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.isoformat() == value else None
        return None

    async def observe(self, db: AsyncSession, session_date, posture) -> bool:
        day = self.valid_date(session_date)
        if day is None or not isinstance(posture, dict):
            return False
        state = posture.get("state")
        if not isinstance(state, str) or state not in KNOWN_STATES:
            return False
        timestamp = datetime.now(timezone.utc)
        try:
            await self.repository.upsert(db, day, state, dict(posture), timestamp)
            await db.commit()
            return True
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.warning("Could not persist observed market posture (%s)", type(exc).__name__)
            return False

    async def history(self, db: AsyncSession, dates: list[date]) -> dict:
        valid_dates = [day for value in dates if (day := self.valid_date(value)) is not None]
        try:
            records = await self.repository.get_dates(db, valid_dates)
            return {"status": "available", "records": [
                {"date": record.session_date.isoformat(), "state": record.state,
                 "instruction": record.payload.get("instruction", ""),
                 "recorded_at": (record.recorded_at.replace(tzinfo=timezone.utc)
                                 if record.recorded_at.tzinfo is None else
                                 record.recorded_at.astimezone(timezone.utc)).isoformat()}
                for record in records
            ]}
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.warning("Could not read observed market posture history (%s)", type(exc).__name__)
            return {"status": "unavailable", "records": []}


market_posture_record_service = MarketPostureRecordService()
