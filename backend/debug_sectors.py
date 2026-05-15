import asyncio
from app.core.database import get_db
from sqlalchemy import select, func
from app.models.stock import Stock, StockMetrics

async def test():
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        # Check if stocks have sectors
        result = await db.execute(
            select(Stock.sector, func.count(Stock.symbol).label('count'))
            .where(Stock.sector.isnot(None))
            .group_by(Stock.sector)
        )
        sectors = result.all()
        print('Sectors with stocks:', sectors)
        
        if sectors:
            sector_name = sectors[0][0]
            print(f'Testing first sector: {sector_name}')
            
            # Test the join query
            stocks_result = await db.execute(
                select(StockMetrics)
                .join(Stock, Stock.symbol == StockMetrics.symbol)
                .where(Stock.sector == sector_name)
            )
            metrics = stocks_result.scalars().all()
            print(f'Metrics for {sector_name}: {len(metrics)} records')
            
            if metrics:
                print(f'Sample metric: distance_to_ema20={metrics[0].distance_to_ema20}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await db.close()

asyncio.run(test())
