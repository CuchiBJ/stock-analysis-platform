import yfinance as yf
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """Client for fetching stock data from Yahoo Finance"""
    
    def __init__(self):
        self.session = None
    
    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch stock information including sector, industry, market cap"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            if not info:
                logger.warning(f"No info found for {symbol}")
                return None
            
            return {
                'symbol': symbol,
                'name': info.get('longName') or info.get('shortName') or symbol,
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'market_cap': info.get('marketCap'),
                'float_shares': info.get('floatShares'),
                'is_adr': info.get('isADR', False)
            }
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return None
    
    def get_multiple_stock_info(self, symbols: list) -> Dict[str, Dict[str, Any]]:
        """Fetch info for multiple stocks"""
        results = {}
        for symbol in symbols:
            info = self.get_stock_info(symbol)
            if info:
                results[symbol] = info
        return results

    def map_yahoo_sector_to_tradingview(self, yahoo_sector: str) -> str:
        """Map Yahoo Finance sector to TradingView granular sector"""
        yahoo_to_tradingview = {
            'Technology': 'Electronic Technology',
            'Healthcare': 'Health Services',
            'Financial Services': 'Finance',
            'Industrials': 'Industrial Services',
            'Consumer Cyclical': 'Consumer Services',
            'Consumer Defensive': 'Consumer Non-Durables',
            'Energy': 'Energy Minerals',
            'Basic Materials': 'Non-Energy Minerals',
            'Real Estate': 'Finance',
            'Communication Services': 'Communications',
            'Utilities': 'Utilities',
            'Transportation': 'Transportation',
            'Producer Manufacturing': 'Producer Manufacturing',
            'Health Technology': 'Health Technology',
            'Consumer Durables': 'Consumer Durables',
            'Retail Trade': 'Retail Trade',
            'Commercial Services': 'Commercial Services',
            'Distribution Services': 'Distribution Services',
            'Process Industries': 'Process Industries',
            'Miscellaneous': 'Miscellaneous'
        }
        return yahoo_to_tradingview.get(yahoo_sector, yahoo_sector)
