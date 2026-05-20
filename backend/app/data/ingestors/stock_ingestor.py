from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.data.sources.polygon_client import PolygonClient
from app.data.sources.yahoo_client import YahooFinanceClient
from app.data.sources.ticker_list_source import TickerListSource
from app.data.sources.tradingview_client import TradingViewClient
from app.data.ingestors.price_ingestor import PriceIngestor
from app.models.stock import Stock
from app.repositories.stock_repository import StockRepository
import logging

logger = logging.getLogger(__name__)


class StockIngestor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.polygon = PolygonClient()
        self.yahoo = YahooFinanceClient()
        self.ticker_source = TickerListSource()
        self.tradingview = TradingViewClient()
        self.repo = StockRepository(db)
        self.price_ingestor = PriceIngestor(db)

    async def ingest_stock_list(
        self,
        market: str = "stocks",
        limit: int = 1000
    ) -> int:
        """Fetch and store stock list from Polygon.io"""
        try:
            data = await self.polygon.get_tickers(market=market, limit=limit)
            
            if "results" not in data:
                logger.error("No results from Polygon API")
                return 0
            
            count = 0
            for ticker in data["results"]:
                # Skip inactive or delisted stocks
                if not ticker.get("active", True):
                    continue
                
                # Check if stock already exists
                existing = await self.repo.get_by_symbol(ticker["ticker"])
                if existing:
                    continue
                
                stock = Stock(
                    symbol=ticker["ticker"],
                    name=ticker["name"] or ticker["ticker"],
                    sector=ticker.get("sector"),
                    industry=ticker.get("industry"),
                    market_cap=ticker.get("market_cap"),
                    float_shares=ticker.get("share_class_shares_outstanding"),
                    is_adr=ticker.get("primary_exchange") == "XNYS",  # Simplified ADR detection
                    is_active=True
                )
                
                await self.repo.create(stock)
                count += 1
                
                # Automatically ingest historical prices for new stocks
                try:
                    await self.price_ingestor.ingest_historical_prices(ticker["ticker"], days=365)
                    logger.info(f"Ingested historical prices for {ticker['ticker']}")
                except Exception as e:
                    logger.warning(f"Failed to ingest historical prices for {ticker['ticker']}: {e}")
                
                if count % 100 == 0:
                    logger.info(f"Ingested {count} stocks")
            
            logger.info(f"Total stocks ingested: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error ingesting stock list: {e}")
            raise
        finally:
            await self.polygon.close()

    async def update_stock_details(self, symbol: str) -> Optional[Stock]:
        """Update stock details for a specific symbol"""
        try:
            data = await self.polygon.get_stock_details(symbol)
            
            if "results" not in data:
                logger.warning(f"No details found for {symbol}")
                return None
            
            ticker = data["results"]
            stock = await self.repo.get_by_symbol(symbol)
            
            if not stock:
                stock = Stock(symbol=symbol)
            
            stock.name = ticker.get("name", symbol)
            stock.sector = ticker.get("sector")
            stock.industry = ticker.get("industry")
            stock.market_cap = ticker.get("market_cap")
            stock.float_shares = ticker.get("share_class_shares_outstanding")
            
            self.db.add(stock)
            await self.db.commit()
            await self.db.refresh(stock)
            
            return stock
            
        except Exception as e:
            logger.error(f"Error updating stock details for {symbol}: {e}")
            raise
        finally:
            await self.polygon.close()

    async def get_active_symbols(self, limit: int = 1000) -> List[str]:
        """Get list of active stock symbols from database"""
        result = await self.db.execute(
            select(Stock.symbol)
            .where(Stock.is_active == True)
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def update_sector_from_yahoo(self, symbol: str) -> Optional[Stock]:
        """Update stock sector and industry from Yahoo Finance"""
        try:
            info = self.yahoo.get_stock_info(symbol)
            if not info:
                logger.warning(f"No Yahoo Finance info for {symbol}")
                return None
            
            stock = await self.repo.get_by_symbol(symbol)
            if not stock:
                logger.warning(f"Stock {symbol} not found in database")
                return None
            
            # Update sector and industry if available
            if info.get('sector'):
                stock.sector = info['sector']
            if info.get('industry'):
                stock.industry = info['industry']
            if info.get('market_cap') and not stock.market_cap:
                stock.market_cap = info['market_cap']
            
            self.db.add(stock)
            await self.db.commit()
            await self.db.refresh(stock)
            
            logger.info(f"Updated sector for {symbol}: {stock.sector}")
            return stock
            
        except Exception as e:
            logger.error(f"Error updating sector for {symbol}: {e}")
            return None

    async def update_all_sectors_from_yahoo(self, limit: int = 1000) -> int:
        """Update sector data for all stocks from Yahoo Finance"""
        symbols = await self.get_active_symbols(limit=limit)
        count = 0
        
        for symbol in symbols:
            stock = await self.update_sector_from_yahoo(symbol)
            if stock and (stock.sector or stock.industry):
                count += 1
            # Small delay to avoid rate limits
            import asyncio
            await asyncio.sleep(0.1)
        
        logger.info(f"Updated sector data for {count} stocks")
        return count

    async def ingest_tickers_from_external(self) -> int:
        """Load tickers from external sources (Wikipedia: S&P 500, NASDAQ-100)"""
        try:
            tickers = self.ticker_source.get_all_tickers()
            
            if not tickers:
                logger.error("No tickers fetched from external sources")
                return 0
            
            count = 0
            for ticker in tickers:
                # Check if stock already exists
                existing = await self.repo.get_by_symbol(ticker)
                if existing:
                    continue
                
                # Create new stock with minimal info
                stock = Stock(
                    symbol=ticker,
                    name=ticker,  # Will be updated from Yahoo later
                    is_active=True
                )
                
                await self.repo.create(stock)
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Ingested {count} tickers from external sources")
            
            logger.info(f"Total tickers ingested from external sources: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error ingesting tickers from external sources: {e}")
            return 0

    async def update_all_stocks_from_yahoo(self) -> int:
        """Update all stocks with data from Yahoo Finance (sector, industry, market cap, name)"""
        try:
            symbols = await self.get_active_symbols(limit=5000)
            count = 0
            
            for symbol in symbols:
                info = self.yahoo.get_stock_info(symbol)
                if info:
                    stock = await self.repo.get_by_symbol(symbol)
                    if stock:
                        # Update stock with Yahoo data
                        if info.get('name'):
                            stock.name = info['name']
                        if info.get('sector'):
                            stock.sector = info['sector']
                        if info.get('industry'):
                            stock.industry = info['industry']
                        if info.get('market_cap') and not stock.market_cap:
                            stock.market_cap = info['market_cap']
                        
                        self.db.add(stock)
                        await self.db.commit()
                        count += 1
                
                # Small delay to avoid rate limits
                import asyncio
                await asyncio.sleep(0.1)
            
            logger.info(f"Updated {count} stocks with Yahoo Finance data")
            return count
            
        except Exception as e:
            logger.error(f"Error updating stocks from Yahoo Finance: {e}")
            return 0

    async def ingest_small_mid_caps_from_tradingview(self, limit_per_category: int = 500) -> int:
        """Ingest small and mid cap stocks from TradingView"""
        try:
            stocks = self.tradingview.get_all_stocks_by_cap(limit_per_category=limit_per_category)
            
            if not stocks:
                logger.error("No stocks fetched from TradingView")
                return 0
            
            count = 0
            for stock_data in stocks:
                symbol = stock_data['symbol']
                
                # Check if stock already exists
                existing = await self.repo.get_by_symbol(symbol)
                if existing:
                    continue
                
                # Create new stock with TradingView data
                stock = Stock(
                    symbol=symbol,
                    name=stock_data.get('name', symbol),
                    market_cap=stock_data.get('market_cap'),
                    is_active=True
                )
                
                await self.repo.create(stock)
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Ingested {count} stocks from TradingView")
            
            logger.info(f"Total stocks ingested from TradingView: {count}")
            return count
            
        except Exception as e:
            logger.error(f"Error ingesting stocks from TradingView: {e}")
            import traceback
            traceback.print_exc()
            return 0
