"""The only application persistence boundary for private journal rows.

Every public operation requires an explicit owner UUID.  There is deliberately
no optional owner parameter and no unscoped fallback: callers cannot obtain a
trade, aggregate input, stop history, or destructive operation without first
supplying the authenticated identity.
"""

from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import JournalStopEvent, JournalTrade


class JournalRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_trades(
        self,
        *,
        owner_user_id: UUID,
        setup: Optional[str] = None,
        context: Optional[str] = None,
        closed_only: bool = False,
        symbol: Optional[str] = None,
        missing_regime_only: bool = False,
    ) -> list[JournalTrade]:
        statement = select(JournalTrade).where(
            JournalTrade.owner_user_id == owner_user_id
        )
        if setup is not None:
            statement = statement.where(JournalTrade.setup == setup)
        if context is not None:
            statement = statement.where(JournalTrade.context == context)
        if closed_only:
            statement = statement.where(JournalTrade.exit_date.is_not(None))
        if symbol is not None:
            statement = statement.where(JournalTrade.symbol == symbol)
        if missing_regime_only:
            statement = statement.where(JournalTrade.regime_at_entry.is_(None))
        statement = statement.order_by(
            JournalTrade.entry_date.desc(), JournalTrade.id.desc()
        )
        return list((await self._db.execute(statement)).scalars().all())

    async def get_trade(
        self,
        *,
        owner_user_id: UUID,
        trade_id: int,
        for_update: bool = False,
    ) -> Optional[JournalTrade]:
        statement = select(JournalTrade).where(
            JournalTrade.id == trade_id,
            JournalTrade.owner_user_id == owner_user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self._db.execute(statement)).scalar_one_or_none()

    async def add_trade(
        self, *, owner_user_id: UUID, trade: JournalTrade
    ) -> JournalTrade:
        if trade.owner_user_id not in (None, owner_user_id):
            raise ValueError("trade owner does not match authenticated owner")
        trade.owner_user_id = owner_user_id
        self._db.add(trade)
        return trade

    async def delete_trade(self, *, owner_user_id: UUID, trade_id: int) -> bool:
        result = await self._db.execute(
            delete(JournalTrade).where(
                JournalTrade.id == trade_id,
                JournalTrade.owner_user_id == owner_user_id,
            )
        )
        return bool(result.rowcount)

    async def delete_all_trades(self, *, owner_user_id: UUID) -> int:
        result = await self._db.execute(
            delete(JournalTrade).where(
                JournalTrade.owner_user_id == owner_user_id
            )
        )
        return int(result.rowcount or 0)

    async def count_trades(
        self,
        *,
        owner_user_id: UUID,
        open_only: bool = False,
        linked_only: bool = False,
        exclude_setups: Sequence[str] = (),
        marked_from_queue_only: bool = False,
    ) -> int:
        statement = select(func.count(JournalTrade.id)).where(
            JournalTrade.owner_user_id == owner_user_id
        )
        if open_only:
            statement = statement.where(JournalTrade.exit_date.is_(None))
        if linked_only:
            statement = statement.where(
                JournalTrade.linked_observation_id.is_not(None)
            )
        if exclude_setups:
            statement = statement.where(
                JournalTrade.setup.notin_(tuple(exclude_setups))
            )
        if marked_from_queue_only:
            statement = statement.where(JournalTrade.from_queue.is_not(None))
        return int((await self._db.execute(statement)).scalar_one())

    async def list_stop_events(
        self, *, owner_user_id: UUID, trade_id: int
    ) -> Optional[list[JournalStopEvent]]:
        trade = await self.get_trade(
            owner_user_id=owner_user_id, trade_id=trade_id
        )
        if trade is None:
            return None
        statement = (
            select(JournalStopEvent)
            .where(JournalStopEvent.trade_id == trade_id)
            .order_by(JournalStopEvent.occurred_at.asc())
        )
        return list((await self._db.execute(statement)).scalars().all())


__all__ = ["JournalRepository"]
