from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from app.models.stock import Stock, StockPrice, StockMetrics


class StockRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        sector: Optional[str] = None
    ) -> List[Stock]:
        query = select(Stock).where(Stock.is_active == True)
        if sector:
            query = query.where(Stock.sector == sector)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_prices(
        self,
        symbol: str,
        days: int = 30
    ) -> List[StockPrice]:
        query = select(StockPrice).where(
            StockPrice.symbol == symbol.upper()
        ).order_by(StockPrice.date.desc()).limit(days)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_latest_metrics(self, symbol: str) -> Optional[StockMetrics]:
        query = select(StockMetrics).where(
            StockMetrics.symbol == symbol.upper()
        ).order_by(StockMetrics.date.desc()).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, stock: Stock) -> Stock:
        self.db.add(stock)
        await self.db.commit()
        await self.db.refresh(stock)
        return stock
