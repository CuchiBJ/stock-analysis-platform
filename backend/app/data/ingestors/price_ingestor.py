from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime, timedelta
from app.data.sources.polygon_client import PolygonClient
from app.models.stock import Stock, StockPrice
from app.data.processors.momentum import calculate_ema, calculate_rsi
import logging

logger = logging.getLogger(__name__)


class PriceIngestor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.polygon = PolygonClient()

    async def ingest_historical_prices(
        self,
        symbol: str,
        days: int = 365
    ) -> int:
        """Fetch and store historical prices for a symbol"""
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get latest date in database
            existing = await self.db.execute(
                select(StockPrice)
                .where(StockPrice.symbol == symbol.upper())
                .order_by(StockPrice.date.desc())
                .limit(1)
            )
            latest_price = existing.scalar_one_or_none()
            
            if latest_price:
                # Only fetch new data since last update
                start_date = datetime.strptime(latest_price.date, "%Y-%m-%d") + timedelta(days=1)
                days = (end_date - start_date).days
            
            if days <= 0:
                logger.info(f"Data for {symbol} is up to date")
                return 0
            
            # Fetch data from Polygon
            data = await self.polygon.get_daily_bars(
                symbol=symbol,
                days=days
            )
            
            if "results" not in data or not data["results"]:
                logger.warning(f"No price data for {symbol}")
                return 0
            
            # Store prices
            count = 0
            for bar in data["results"]:
                date = datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d")
                
                # Check if already exists
                existing = await self.db.execute(
                    select(StockPrice).where(
                        and_(
                            StockPrice.symbol == symbol.upper(),
                            StockPrice.date == date
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                
                price = StockPrice(
                    symbol=symbol.upper(),
                    date=date,
                    open=bar["o"],
                    high=bar["h"],
                    low=bar["l"],
                    close=bar["c"],
                    volume=bar["v"],
                    vwap=bar.get("vw")
                )
                
                self.db.add(price)
                count += 1
            
            await self.db.commit()
            logger.info(f"Ingested {count} price records for {symbol}")
            return count
            
        except Exception as e:
            logger.error(f"Error ingesting prices for {symbol}: {e}")
            await self.db.rollback()
            raise
        finally:
            await self.polygon.close()

    async def ingest_latest_prices(self, symbols: List[str] = None) -> int:
        """Fetch latest prices for multiple symbols (last 5 days)"""
        total_count = 0
        
        if symbols is None:
            # Get all active symbols
            from app.data.ingestors.stock_ingestor import StockIngestor
            ingestor = StockIngestor(self.db)
            symbols = await ingestor.get_active_symbols(limit=500)
        
        for symbol in symbols:
            try:
                count = await self.ingest_historical_prices(symbol, days=5)
                total_count += count
            except Exception as e:
                logger.error(f"Failed to ingest prices for {symbol}: {e}")
                continue
        
        return total_count

    async def ingest_intraday_prices(self, symbols: List[str] = None) -> int:
        """Fetch intraday prices for multiple symbols (real-time)"""
        total_count = 0
        
        if symbols is None:
            # Get all active symbols (all stocks for complete price updates)
            from app.data.ingestors.stock_ingestor import StockIngestor
            ingestor = StockIngestor(self.db)
            symbols = await ingestor.get_active_symbols(limit=None)  # All active stocks
        
        for symbol in symbols:
            try:
                count = await self._ingest_intraday_single(symbol)
                total_count += count
            except Exception as e:
                logger.error(f"Failed to ingest intraday prices for {symbol}: {e}")
                continue
        
        return total_count

    async def _ingest_intraday_single(self, symbol: str) -> int:
        """Fetch and store intraday prices for a single symbol"""
        try:
            # Get intraday data from last 60 minutes
            data = await self.polygon.get_intraday_bars(
                symbol=symbol,
                timespan="minute",
                multiplier=1,
                minutes=60
            )
            
            if "results" not in data or not data["results"]:
                logger.warning(f"No intraday data for {symbol}")
                return 0
            
            # Store/update the most recent price
            latest_bar = data["results"][0]
            timestamp = datetime.fromtimestamp(latest_bar["t"] / 1000)
            date_str = timestamp.strftime("%Y-%m-%d")
            
            # Check if today's record exists
            existing = await self.db.execute(
                select(StockPrice).where(
                    and_(
                        StockPrice.symbol == symbol.upper(),
                        StockPrice.date == date_str
                    )
                )
            )
            existing_price = existing.scalar_one_or_none()
            
            if existing_price:
                # Update with latest intraday price
                existing_price.open = latest_bar["o"]
                existing_price.high = latest_bar["h"]
                existing_price.low = latest_bar["l"]
                existing_price.close = latest_bar["c"]
                existing_price.volume = latest_bar["v"]
                existing_price.vwap = latest_bar.get("vw")
            else:
                # Create new record
                price = StockPrice(
                    symbol=symbol.upper(),
                    date=date_str,
                    open=latest_bar["o"],
                    high=latest_bar["h"],
                    low=latest_bar["l"],
                    close=latest_bar["c"],
                    volume=latest_bar["v"],
                    vwap=latest_bar.get("vw")
                )
                self.db.add(price)
            
            await self.db.commit()
            logger.info(f"Updated intraday price for {symbol}: ${latest_bar['c']}")
            return 1
            
        except Exception as e:
            logger.error(f"Error ingesting intraday prices for {symbol}: {e}")
            await self.db.rollback()
            raise

    async def get_price_history(
        self,
        symbol: str,
        days: int = 200
    ) -> List[StockPrice]:
        """Get price history for calculations"""
        result = await self.db.execute(
            select(StockPrice)
            .where(StockPrice.symbol == symbol.upper())
            .order_by(StockPrice.date.desc())
            .limit(days)
        )
        return result.scalars().all()
