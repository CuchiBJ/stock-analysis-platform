from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_posture_record import MarketPostureRecord


class MarketPostureRecordRepository:
    async def upsert(
        self, db: AsyncSession, session_date: date, state: str,
        payload: dict, recorded_at: datetime,
    ) -> None:
        values = {"session_date": session_date, "state": state,
                  "payload": payload, "recorded_at": recorded_at}
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = pg_insert(MarketPostureRecord).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[MarketPostureRecord.session_date],
                set_={"state": statement.excluded.state,
                      "payload": statement.excluded.payload,
                      "recorded_at": statement.excluded.recorded_at,
                      "updated_at": statement.excluded.recorded_at},
                where=statement.excluded.recorded_at > MarketPostureRecord.recorded_at,
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(MarketPostureRecord).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[MarketPostureRecord.session_date],
                set_={"state": statement.excluded.state,
                      "payload": statement.excluded.payload,
                      "recorded_at": statement.excluded.recorded_at,
                      "updated_at": statement.excluded.recorded_at},
                where=statement.excluded.recorded_at > MarketPostureRecord.recorded_at,
            )
        else:
            raise ValueError(f"Unsupported database dialect: {dialect}")
        await db.execute(statement)

    async def get_dates(self, db: AsyncSession, dates: list[date]) -> list[MarketPostureRecord]:
        if not dates:
            return []
        result = await db.execute(
            select(MarketPostureRecord)
            .where(MarketPostureRecord.session_date.in_(dates))
            .order_by(MarketPostureRecord.session_date)
        )
        return list(result.scalars().all())
