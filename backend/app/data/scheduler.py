from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator
from datetime import datetime, time
import pytz
import logging
import asyncio

logger = logging.getLogger(__name__)


class DataScheduler:
    def __init__(self, db_factory):
        """
        db_factory: callable that returns AsyncSession
        """
        self.db_factory = db_factory
        self.scheduler = AsyncIOScheduler()

    async def ingest_stock_list(self):
        """Daily task: ingest stock list"""
        async with self.db_factory() as db:
            ingestor = StockIngestor(db)
            try:
                count = await ingestor.ingest_stock_list()
                logger.info(f"Stock list ingestion complete: {count} stocks")
            except Exception as e:
                logger.error(f"Stock list ingestion failed: {e}")

    async def ingest_latest_prices(self):
        """Task: ingest intraday prices (runs every 15min during market hours)"""
        # Check if it's market hours (9:30 AM - 4:00 PM ET)
        et_tz = pytz.timezone('US/Eastern')
        now = datetime.now(et_tz)
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        
        # Skip if outside market hours
        if not (market_open <= current_time <= market_close):
            logger.info(f"Skipping intraday price ingestion - outside market hours (current time: {current_time})")
            return
        
        async with self.db_factory() as db:
            ingestor = PriceIngestor(db)
            try:
                count = await ingestor.ingest_intraday_prices()
                logger.info(f"Intraday prices ingestion complete: {count} symbols at {now.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.error(f"Intraday prices ingestion failed: {e}")

    async def calculate_metrics(self):
        """Daily task: calculate metrics"""
        async with self.db_factory() as db:
            calculator = MetricsCalculator(db)
            
            try:
                # Get symbols needing update
                symbols = await calculator.get_symbols_needing_update(hours=24)
                
                if not symbols:
                    # If none need update, calculate for top 100 active stocks
                    ingestor = StockIngestor(db)
                    symbols = await ingestor.get_active_symbols(limit=100)
                
                count = await calculator.calculate_metrics_batch(symbols)
                logger.info(f"Metrics calculation complete: {count} symbols")
            except Exception as e:
                logger.error(f"Metrics calculation failed: {e}")

    def start(self):
        """Start the scheduler"""
        # Ingest stock list daily at 2 AM
        self.scheduler.add_job(
            self.ingest_stock_list,
            CronTrigger(hour=2, minute=0),
            id='ingest_stock_list',
            replace_existing=True
        )
        
        # Ingest intraday prices every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
        self.scheduler.add_job(
            self.ingest_latest_prices,
            IntervalTrigger(minutes=15),
            id='ingest_latest_prices',
            replace_existing=True
        )
        
        # Calculate metrics daily at 7 PM
        self.scheduler.add_job(
            self.calculate_metrics,
            CronTrigger(hour=19, minute=0),
            id='calculate_metrics',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Data scheduler started - intraday prices update every 15min during market hours (9:30 AM - 4:00 PM ET)")
        
        # Trigger initial price update if within market hours
        asyncio.create_task(self._initial_price_update())
    
    async def _initial_price_update(self):
        """Initial price update on startup if within market hours"""
        await asyncio.sleep(2)  # Wait for scheduler to start
        et_tz = pytz.timezone('US/Eastern')
        now = datetime.now(et_tz)
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        
        if market_open <= current_time <= market_close:
            logger.info(f"Triggering initial price update on startup (current time: {current_time})")
            await self.ingest_latest_prices()

    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Data scheduler shutdown")
