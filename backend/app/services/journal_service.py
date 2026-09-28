"""Owner-scoped orchestration for journal reads and aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import JournalStopEvent, JournalTrade
from app.repositories.journal_repository import JournalRepository


def group_decisions(
    trades: Sequence[JournalTrade],
) -> dict[int, list[JournalTrade]]:
    """Pure decision grouping over an already owner-scoped collection."""
    decisions: dict[int, list[JournalTrade]] = {}
    for trade in trades:
        decision_id = (
            trade.parent_trade_id
            if trade.parent_trade_id is not None
            else trade.id
        )
        decisions.setdefault(decision_id, []).append(trade)
    return decisions


@dataclass(frozen=True)
class JournalListing:
    rows: list[JournalTrade]
    decisions: dict[int, list[JournalTrade]]


@dataclass(frozen=True)
class JournalStatisticsData:
    closed_rows: list[JournalTrade]
    all_rows: list[JournalTrade]
    decisions: dict[int, list[JournalTrade]]
    open_count: int
    linked_count: int
    provenance_total_count: int
    provenance_marked_count: int


class JournalService:
    """Business boundary permanently bound to one authenticated owner."""

    def __init__(self, db: AsyncSession, owner_user_id: UUID):
        self.db = db
        self.owner_user_id = owner_user_id
        self.repository = JournalRepository(db)

    async def listing(
        self,
        *,
        setup: Optional[str] = None,
        context: Optional[str] = None,
        closed_only: bool = False,
    ) -> JournalListing:
        rows = await self.repository.list_trades(
            owner_user_id=self.owner_user_id,
            setup=setup,
            context=context,
            closed_only=closed_only,
        )
        all_rows = await self.repository.list_trades(
            owner_user_id=self.owner_user_id
        )
        return JournalListing(rows=rows, decisions=group_decisions(all_rows))

    async def statistics(
        self, *, exclude_setups: Sequence[str] = ()
    ) -> JournalStatisticsData:
        closed_rows = await self.repository.list_trades(
            owner_user_id=self.owner_user_id, closed_only=True
        )
        all_rows = await self.repository.list_trades(
            owner_user_id=self.owner_user_id
        )
        excluded = frozenset(exclude_setups)
        if excluded:
            closed_rows = [
                trade for trade in closed_rows if trade.setup not in excluded
            ]
            all_rows = [
                trade for trade in all_rows if trade.setup not in excluded
            ]
        open_count = await self.repository.count_trades(
            owner_user_id=self.owner_user_id,
            open_only=True,
            exclude_setups=exclude_setups,
        )
        linked_count = await self.repository.count_trades(
            owner_user_id=self.owner_user_id,
            linked_only=True,
            exclude_setups=exclude_setups,
        )
        provenance_total_count = await self.repository.count_trades(
            owner_user_id=self.owner_user_id,
            exclude_setups=exclude_setups,
        )
        provenance_marked_count = await self.repository.count_trades(
            owner_user_id=self.owner_user_id,
            exclude_setups=exclude_setups,
            marked_from_queue_only=True,
        )
        return JournalStatisticsData(
            closed_rows=closed_rows,
            all_rows=all_rows,
            decisions=group_decisions(all_rows),
            open_count=open_count,
            linked_count=linked_count,
            provenance_total_count=provenance_total_count,
            provenance_marked_count=provenance_marked_count,
        )

    async def export_decisions(self) -> dict[int, list[JournalTrade]]:
        rows = await self.repository.list_trades(
            owner_user_id=self.owner_user_id
        )
        return group_decisions(rows)

    async def get_trade(
        self, trade_id: int, *, for_update: bool = False
    ) -> Optional[JournalTrade]:
        return await self.repository.get_trade(
            owner_user_id=self.owner_user_id,
            trade_id=trade_id,
            for_update=for_update,
        )

    async def stop_history(
        self, trade_id: int
    ) -> Optional[list[JournalStopEvent]]:
        return await self.repository.list_stop_events(
            owner_user_id=self.owner_user_id, trade_id=trade_id
        )

    async def delete_trade(self, trade_id: int) -> bool:
        return await self.repository.delete_trade(
            owner_user_id=self.owner_user_id, trade_id=trade_id
        )


__all__ = [
    "JournalListing",
    "JournalService",
    "JournalStatisticsData",
    "group_decisions",
]
