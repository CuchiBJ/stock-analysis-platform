import asyncio
from app.core.database import get_db
from sqlalchemy import select, func
from app.models.stock import Stock, StockMetrics

async def test():
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    # Test 1: Check if stocks have sectors
    result = await db.execute(
        select(Stock.sector, func.count(Stock.symbol).label('count'))
        .where(Stock.sector.isnot(None))
        .group_by(Stock.sector)
    )
    sectors = result.all()
    print('Sectors with stocks:', sectors)
    
    if sectors:
        # Test 2: Check if stocks have metrics
        result2 = await db.execute(
            select(StockMetrics)
            .join(Stock, Stock.symbol == StockMetrics.symbol)
            .where(Stock.sector == sectors[0][0])
        )
        metrics = result2.scalars().all()
        print(f'Metrics for first sector: {len(metrics)} records')
    else:
        print('No sectors found')
    
    await db.close()

asyncio.run(test())
