from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.data.ingestors.stock_ingestor import StockIngestor
from app.data.ingestors.price_ingestor import PriceIngestor
from app.data.ingestors.metrics_calculator import MetricsCalculator
from app.core.config import settings
from datetime import datetime, time
import pytz
import logging
import asyncio

logger = logging.getLogger(__name__)


class DataScheduler:
    def __init__(self, database_url=None):
        if database_url:
            self.engine = create_async_engine(database_url, echo=False)
            self.async_session_maker = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        else:
            self.engine = None
            self.async_session_maker = None
        self._running = False

    def _get_db(self):
        """Get database session"""
        if self.async_session_maker:
            return self.async_session_maker()
        raise RuntimeError("Database not initialized")

    async def trigger_metrics_update(self, limit=100):
        """Manually trigger metrics calculation"""
        async with self._get_db() as db:
            ingestor = StockIngestor(db)
            symbols = await ingestor.get_active_symbols(limit=limit)
            logger.info(f"Calculating metrics for {len(symbols)} symbols...")
            
            calculator = MetricsCalculator(db)
            count = await calculator.calculate_metrics_batch(symbols)
            logger.info(f"Metrics calculated for {count} symbols")
            return count

    async def _scheduler_loop(self):
        """Background scheduler loop that executes jobs based on time"""
        logger.info("Scheduler loop started")
        et_tz = pytz.timezone('US/Eastern')
        market_open = time(9, 30)
        market_close = time(16, 0)
        
        last_price_update = None
        last_metrics_update = None
        
        # Trigger initial metrics update immediately
        logger.info("Triggering initial metrics update")
        await self.trigger_metrics_update(limit=3125)
        last_metrics_update = datetime.now(et_tz)
        
        while self._running:
            now = datetime.now(et_tz)
            current_time = now.time()
            
            # Check if within market hours
            if market_open <= current_time <= market_close:
                # Price update every 15 minutes
                if last_price_update is None or (now - last_price_update).total_seconds() >= 900:
                    logger.info(f"Triggering price update (current time: {current_time})")
                    # Run price update in background to not block metrics
                    asyncio.create_task(self._update_prices())
                    last_price_update = now
                
                # Metrics update every 30 minutes
                if last_metrics_update is None or (now - last_metrics_update).total_seconds() >= 1800:
                    logger.info(f"Triggering metrics update (current time: {current_time})")
                    await self.trigger_metrics_update(limit=3125)
                    last_metrics_update = now
            else:
                logger.info(f"Outside market hours (current time: {current_time})")
            
            # Sleep for 30 seconds before checking again
            await asyncio.sleep(30)

    async def _update_prices(self):
        """Update prices"""
        async with self._get_db() as db:
            ingestor = PriceIngestor(db)
            try:
                count = await ingestor.ingest_intraday_prices()
                logger.info(f"Price update complete: {count} symbols")
            except Exception as e:
                logger.error(f"Price update failed: {e}")

    async def run(self):
        """Run the scheduler loop"""
        self._running = True
        try:
            await self._scheduler_loop()
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        finally:
            self._running = False
            if self.engine:
                await self.engine.dispose()

    def stop(self):
        """Stop the scheduler"""
        self._running = False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    scheduler = DataScheduler(settings.database_url)
    try:
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.stop()
