from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.index import Index
from app.schemas.index import Index, IndexBase
from app.repositories.base import BaseRepository


class IndexRepository(BaseRepository[Index, IndexBase, IndexBase]):
    async def get_by_symbol(self, db: AsyncSession, symbol: str) -> Optional[Index]:
        result = await db.execute(select(Index).where(Index.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_all_active(self, db: AsyncSession) -> List[Index]:
        result = await db.execute(
            select(Index).order_by(Index.symbol)
        )
        return result.scalars().all()
