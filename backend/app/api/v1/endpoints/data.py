from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator

router = APIRouter()


@router.post("/ingest/stocks")
async def ingest_stocks(
    background_tasks: BackgroundTasks,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    """Trigger stock list ingestion (background task)"""
    async def task():
        ingestor = StockIngestor(db)
        await ingestor.ingest_stock_list(limit=limit)
    
    background_tasks.add_task(task)
    return {"message": "Stock ingestion started"}


@router.post("/ingest/prices/{symbol}")
async def ingest_prices(
    symbol: str,
    background_tasks: BackgroundTasks,
    days: int = 365,
    db: AsyncSession = Depends(get_db)
):
    """Trigger price ingestion for a symbol (background task)"""
    async def task():
        ingestor = PriceIngestor(db)
        await ingestor.ingest_historical_prices(symbol, days)
    
    background_tasks.add_task(task)
    return {"message": f"Price ingestion started for {symbol}"}


@router.post("/ingest/prices/latest")
async def ingest_latest_prices(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger latest prices ingestion for all active stocks (background task)"""
    async def task():
        ingestor = StockIngestor(db)
        price_ingestor = PriceIngestor(db)
        symbols = await ingestor.get_active_symbols(limit=500)
        await price_ingestor.ingest_latest_prices(symbols)
    
    background_tasks.add_task(task)
    return {"message": "Latest prices ingestion started"}


@router.post("/ingest/prices/missing")
async def ingest_missing_prices(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger historical prices ingestion for stocks without price data (background task)"""
    async def task():
        ingestor = StockIngestor(db)
        price_ingestor = PriceIngestor(db)
        
        # Get all active symbols
        all_symbols = await ingestor.get_active_symbols(limit=5000)
        logger.info(f"Total active symbols: {len(all_symbols)}")
        
        # Get symbols that already have price data
        from sqlalchemy import select, text
        result = await db.execute(
            text("SELECT DISTINCT symbol FROM stock_prices")
        )
        symbols_with_prices = {row[0] for row in result}
        logger.info(f"Symbols with prices: {len(symbols_with_prices)}")
        
        # Filter to get symbols without price data
        symbols = [s for s in all_symbols if s not in symbols_with_prices][:500]
        logger.info(f"Symbols without prices: {len(symbols)}")
        logger.info(f"First 10 symbols without prices: {symbols[:10]}")
        
        for symbol in symbols:
            try:
                await price_ingestor.ingest_historical_prices(symbol, days=365)
                logger.info(f"Loaded prices for {symbol}")
                # Small delay to avoid rate limits
                import asyncio
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error loading prices for {symbol}: {e}")
        
        logger.info(f"Price ingestion complete for {len(symbols)} stocks")
    
    background_tasks.add_task(task)
    return {"message": "Historical prices ingestion started for stocks without price data"}


@router.get("/debug/missing-prices")
async def debug_missing_prices(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to see which symbols are missing prices"""
    ingestor = StockIngestor(db)
    
    # Get all active symbols
    all_symbols = await ingestor.get_active_symbols(limit=5000)
    
    # Get symbols that already have price data
    from sqlalchemy import select, text
    result = await db.execute(
        text("SELECT DISTINCT symbol FROM stock_prices")
    )
    symbols_with_prices = {row[0] for row in result}
    
    # Filter to get symbols without price data
    symbols = [s for s in all_symbols if s not in symbols_with_prices][:500]
    
    return {
        "total_active": len(all_symbols),
        "with_prices": len(symbols_with_prices),
        "without_prices": len(symbols),
        "first_10_without_prices": symbols[:10]
    }


@router.post("/calculate/metrics/{symbol}")
async def calculate_metrics(
    symbol: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger metrics calculation for a symbol (background task)"""
    async def task():
        calculator = MetricsCalculator(db)
        await calculator.calculate_metrics_for_symbol(symbol)
    
    background_tasks.add_task(task)
    return {"message": f"Metrics calculation started for {symbol}"}


@router.post("/calculate/metrics/all")
async def calculate_metrics_all(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Calculate metrics for all stocks with prices"""
    calculator = MetricsCalculator(db)
    
    async def task():
        # Get symbols that have prices but no metrics
        result = await db.execute(
            text("""
                SELECT DISTINCT sp.symbol 
                FROM stock_prices sp 
                LEFT JOIN stock_metrics sm ON sp.symbol = sm.symbol 
                WHERE sm.symbol IS NULL
                LIMIT 1000
            """)
        )
        symbols = [row[0] for row in result]
        
        logger.info(f"Calculating metrics for {len(symbols)} symbols with prices but no metrics")
        count = await calculator.calculate_metrics_batch(symbols)
        logger.info(f"Metrics calculation complete: {count} symbols")
    
    background_tasks.add_task(task)
    return {"message": "Metrics calculation started for stocks with prices"}


@router.post("/update/stock-details/{symbol}")
async def update_stock_details(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Update stock details (market cap, sector, etc.) from Polygon.io"""
    ingestor = StockIngestor(db)
    try:
        stock = await ingestor.update_stock_details(symbol)
        if stock:
            return {"message": f"Updated details for {symbol}", "market_cap": stock.market_cap}
        else:
            return {"message": f"No details found for {symbol}"}
    except Exception as e:
        return {"message": f"Error updating details for {symbol}: {str(e)}"}


@router.post("/update/sectors/yahoo/all")
async def update_all_sectors_yahoo(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Update sector data for all stocks from Yahoo Finance (background task)"""
    ingestor = StockIngestor(db)
    
    async def task():
        count = await ingestor.update_all_sectors_from_yahoo(limit=1014)
        logger.info(f"Sector update complete: {count} stocks updated")
    
    background_tasks.add_task(task)
    return {"message": "Sector update started for all stocks from Yahoo Finance"}


@router.post("/update/sector/yahoo/{symbol}")
async def update_sector_yahoo(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Update stock sector from Yahoo Finance"""
    ingestor = StockIngestor(db)
    try:
        stock = await ingestor.update_sector_from_yahoo(symbol)
        if stock:
            return {"message": f"Updated sector for {symbol}", "sector": stock.sector, "industry": stock.industry}
        else:
            return {"message": f"No sector data found for {symbol}"}
    except Exception as e:
        return {"message": f"Error updating sector for {symbol}: {str(e)}"}


@router.post("/ingest/tickers/external")
async def ingest_tickers_external(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Load tickers from external sources (Wikipedia: S&P 500, NASDAQ-100)"""
    ingestor = StockIngestor(db)
    
    async def task():
        count = await ingestor.ingest_tickers_from_external()
        logger.info(f"Ticker ingestion complete: {count} new tickers added")
    
    background_tasks.add_task(task)
    return {"message": "Ticker ingestion started from external sources (S&P 500, NASDAQ-100)"}


@router.post("/update/stocks/yahoo/all")
async def update_all_stocks_yahoo(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Update all stocks with data from Yahoo Finance (sector, industry, market cap, name)"""
    ingestor = StockIngestor(db)
    
    async def task():
        count = await ingestor.update_all_stocks_from_yahoo()
        logger.info(f"Stock update complete: {count} stocks updated with Yahoo data")
    
    background_tasks.add_task(task)
    return {"message": "Stock update started from Yahoo Finance for all stocks"}


@router.post("/ingest/small-mid-caps/tradingview")
async def ingest_small_mid_caps_tradingview(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Ingest small and mid cap stocks from TradingView"""
    ingestor = StockIngestor(db)
    
    async def task():
        count = await ingestor.ingest_small_mid_caps_from_tradingview(limit_per_category=500)
        logger.info(f"Small/mid cap ingestion complete: {count} stocks added")
    
    background_tasks.add_task(task)
    return {"message": "Small/mid cap ingestion started from TradingView"}


@router.get("/top-symbols")
async def get_top_symbols(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Return top symbols by pullback quality score for price monitoring."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT DISTINCT ON (sm.symbol) sm.symbol
            FROM stock_metrics sm
            WHERE sm.pullback_quality_score IS NOT NULL
              AND sm.avg_volume_10d >= 500000
              AND sm.current_price >= 5.0
            ORDER BY sm.symbol, sm.pullback_quality_score DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    symbols = [row[0] for row in result.fetchall()]
    if not symbols:
        # Fallback to most active stocks when no metrics yet
        result = await db.execute(
            text("""
                SELECT DISTINCT symbol FROM stock_prices
                ORDER BY symbol LIMIT :limit
            """),
            {"limit": limit}
        )
        symbols = [row[0] for row in result.fetchall()]
    return {"symbols": symbols}
