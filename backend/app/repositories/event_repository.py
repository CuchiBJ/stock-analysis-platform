from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from app.models.event import Event
from app.schemas.calendar import Event, EventBase
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event, EventBase, EventBase]):
    async def get_by_date_range(
        self, 
        db: AsyncSession, 
        start_date: date, 
        end_date: date
    ) -> List[Event]:
        result = await db.execute(
            select(Event)
            .where(Event.event_date >= start_date)
            .where(Event.event_date <= end_date)
            .order_by(Event.event_date)
        )
        return result.scalars().all()

    async def get_upcoming(self, db: AsyncSession, days: int = 30) -> List[Event]:
        from datetime import datetime, timedelta
        end_date = datetime.now().date() + timedelta(days=days)
        result = await db.execute(
            select(Event)
            .where(Event.event_date <= end_date)
            .order_by(Event.event_date)
        )
        return result.scalars().all()
