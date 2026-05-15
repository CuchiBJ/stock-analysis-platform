import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, func
from app.models.stock import Stock, StockMetrics

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"

async def check_data():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check how many stocks have metrics
        result = await session.execute(
            select(func.count()).select_from(Stock).join(StockMetrics, Stock.symbol == StockMetrics.symbol)
        )
        total_with_metrics = result.scalar()
        print(f"Total stocks with metrics: {total_with_metrics}")
        
        # Check how many stocks pass each filter
        filters = {
            "is_active": Stock.is_active == True,
            "price > sma50": StockMetrics.current_price > StockMetrics.sma50,
            "market_cap 600M-200B": and_(Stock.market_cap >= 600000000, Stock.market_cap <= 200000000000),
            "perf_1y > 30%": StockMetrics.perf_1y > 30,
            "sma150 > sma200": StockMetrics.sma150 > StockMetrics.sma200,
            "price > sma150": StockMetrics.current_price > StockMetrics.sma150,
            "avg_volume_10d > 1M": StockMetrics.avg_volume_10d > 1000000,
            "sma50 > sma150": StockMetrics.sma50 > StockMetrics.sma150,
            "price > 10": StockMetrics.current_price > 10,
            "perf_1w < 0": StockMetrics.perf_1w < 0,
            "adr_percent > 4": StockMetrics.adr_percent > 4,
        }
        
        for filter_name, condition in filters.items():
            result = await session.execute(
                select(func.count()).select_from(Stock).join(StockMetrics, Stock.symbol == StockMetrics.symbol).where(condition)
            )
            count = result.scalar()
            print(f"{filter_name}: {count} stocks")
        
        # Check how many stocks have NULL adr_percent
        result = await session.execute(
            select(func.count()).select_from(StockMetrics).where(StockMetrics.adr_percent.is_(None))
        )
        null_adr = result.scalar()
        print(f"Stocks with NULL adr_percent: {null_adr}")
        
        # Check how many stocks have adr_percent = 0
        result = await session.execute(
            select(func.count()).select_from(StockMetrics).where(StockMetrics.adr_percent == 0)
        )
        zero_adr = result.scalar()
        print(f"Stocks with adr_percent = 0: {zero_adr}")
        
        # Check current custom screener results
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                Stock.is_active == True,
                StockMetrics.current_price > StockMetrics.sma50,
                Stock.market_cap >= 600000000,
                Stock.market_cap <= 200000000000,
                StockMetrics.perf_1y > 30,
                StockMetrics.sma150 > StockMetrics.sma200,
                StockMetrics.current_price > StockMetrics.sma150,
                StockMetrics.avg_volume_10d > 1000000,
                StockMetrics.sma50 > StockMetrics.sma150,
                StockMetrics.current_price > 10,
                StockMetrics.perf_1w < 0,
                StockMetrics.adr_percent > 4
            )
        )
        
        result = await session.execute(query)
        rows = result.all()
        print(f"\nCurrent custom screener (without 52W filters): {len(rows)} stocks")
        
        for stock, metrics in rows[:10]:
            print(f"  {stock.symbol}: adr_percent={metrics.adr_percent}, perf_1y={metrics.perf_1y}, perf_1w={metrics.perf_1w}")

if __name__ == "__main__":
    asyncio.run(check_data())
