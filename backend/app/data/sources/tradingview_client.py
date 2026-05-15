from tradingview_screener import Query, col
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TradingViewClient:
    """Fetch stock data from TradingView screener API"""
    
    def __init__(self):
        pass
    
    def get_small_cap_stocks(self, limit: int = 500) -> List[dict]:
        """Fetch small cap stocks (market cap < 2B) from TradingView"""
        try:
            # Small cap: market cap between 300M and 2B
            data = (Query()
                   .select('name', 'close', 'volume', 'market_cap_basic')
                   .where(col('market_cap_basic').between(300_000_000, 2_000_000_000))
                   .order_by('volume', ascending=False)
                   .limit(limit)
                   .get_scanner_data())
            
            if not data or len(data) < 2:
                logger.warning("No small cap data returned from TradingView")
                return []
            
            # Extract tickers from the dataframe (second element of tuple)
            df = data[1]
            tickers = []
            
            for _, row in df.iterrows():
                ticker = row.get('ticker', '')
                if ticker:
                    # Remove exchange prefix (e.g., "NASDAQ:" -> "")
                    symbol = ticker.split(':')[-1]
                    tickers.append({
                        'symbol': symbol,
                        'name': row.get('name', symbol),
                        'market_cap': row.get('market_cap_basic')
                    })
            
            logger.info(f"Fetched {len(tickers)} small cap stocks from TradingView")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching small cap stocks from TradingView: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_mid_cap_stocks(self, limit: int = 500) -> List[dict]:
        """Fetch mid cap stocks (market cap 2B-10B) from TradingView"""
        try:
            # Mid cap: market cap between 2B and 10B
            data = (Query()
                   .select('name', 'close', 'volume', 'market_cap_basic')
                   .where(col('market_cap_basic').between(2_000_000_000, 10_000_000_000))
                   .order_by('volume', ascending=False)
                   .limit(limit)
                   .get_scanner_data())
            
            if not data or len(data) < 2:
                logger.warning("No mid cap data returned from TradingView")
                return []
            
            df = data[1]
            tickers = []
            
            for _, row in df.iterrows():
                ticker = row.get('ticker', '')
                if ticker:
                    symbol = ticker.split(':')[-1]
                    tickers.append({
                        'symbol': symbol,
                        'name': row.get('name', symbol),
                        'market_cap': row.get('market_cap_basic')
                    })
            
            logger.info(f"Fetched {len(tickers)} mid cap stocks from TradingView")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching mid cap stocks from TradingView: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_all_stocks_by_cap(self, limit_per_category: int = 500) -> List[dict]:
        """Fetch all stocks categorized by market cap"""
        all_stocks = []
        
        # Get small caps
        small_caps = self.get_small_cap_stocks(limit=limit_per_category)
        all_stocks.extend(small_caps)
        
        # Get mid caps
        mid_caps = self.get_mid_cap_stocks(limit=limit_per_category)
        all_stocks.extend(mid_caps)
        
        # Remove duplicates by symbol
        unique_stocks = {}
        for stock in all_stocks:
            symbol = stock['symbol']
            if symbol not in unique_stocks:
                unique_stocks[symbol] = stock
        
        result = list(unique_stocks.values())
        logger.info(f"Total unique stocks from TradingView: {len(result)}")
        return result
