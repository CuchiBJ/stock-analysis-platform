import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


class TickerListSource:
    """Fetch stock ticker lists from external sources (Wikipedia, yfinance, etc.)"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_sp500_tickers(self) -> List[str]:
        """Fetch S&P 500 tickers using yfinance"""
        try:
            # Use pandas to read Wikipedia table
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            headers = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, header=0)
            df = tables[0]
            tickers = df['Symbol'].tolist()
            
            # Clean tickers
            clean_tickers = []
            for ticker in tickers:
                if isinstance(ticker, str):
                    ticker = ticker.replace('.', '').replace('-', '')
                    if ticker and ticker.isalpha():
                        clean_tickers.append(ticker.upper())
            
            logger.info(f"Fetched {len(clean_tickers)} S&P 500 tickers")
            return clean_tickers
        except Exception as e:
            logger.error(f"Error fetching S&P 500 tickers: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_russell2000_tickers(self) -> List[str]:
        """Fetch Russell 2000 tickers using yfinance"""
        try:
            # Use pandas to read Wikipedia table
            url = "https://en.wikipedia.org/wiki/Russell_2000"
            headers = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, header=0)
            
            # Russell 2000 page has multiple tables, find the one with tickers
            for df in tables:
                if 'Ticker' in df.columns or 'Symbol' in df.columns:
                    ticker_col = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
                    tickers = df[ticker_col].tolist()
                    
                    # Clean tickers
                    clean_tickers = []
                    for ticker in tickers:
                        if isinstance(ticker, str):
                            ticker = ticker.replace('.', '').replace('-', '')
                            if ticker and ticker.isalpha():
                                clean_tickers.append(ticker.upper())
                    
                    logger.info(f"Fetched {len(clean_tickers)} Russell 2000 tickers")
                    return clean_tickers
            
            logger.warning("Could not find ticker table for Russell 2000")
            return []
        except Exception as e:
            logger.error(f"Error fetching Russell 2000 tickers: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_russell_midcap_tickers(self) -> List[str]:
        """Fetch Russell Midcap tickers using yfinance"""
        try:
            # Use pandas to read Wikipedia table
            url = "https://en.wikipedia.org/wiki/Russell_Midcap_Index"
            headers = {'User-Agent': 'Mozilla/5.0'}
            tables = pd.read_html(url, header=0)
            
            # Find the table with tickers
            for df in tables:
                if 'Ticker' in df.columns or 'Symbol' in df.columns:
                    ticker_col = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
                    tickers = df[ticker_col].tolist()
                    
                    # Clean tickers
                    clean_tickers = []
                    for ticker in tickers:
                        if isinstance(ticker, str):
                            ticker = ticker.replace('.', '').replace('-', '')
                            if ticker and ticker.isalpha():
                                clean_tickers.append(ticker.upper())
                    
                    logger.info(f"Fetched {len(clean_tickers)} Russell Midcap tickers")
                    return clean_tickers
            
            logger.warning("Could not find ticker table for Russell Midcap")
            return []
        except Exception as e:
            logger.error(f"Error fetching Russell Midcap tickers: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_nasdaq100_tickers(self) -> List[str]:
        """Fetch NASDAQ-100 tickers from Wikipedia"""
        try:
            url = "https://en.wikipedia.org/wiki/NASDAQ-100"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'wikitable sortable'})
            
            tickers = []
            for row in table.find_all('tr')[1:]:  # Skip header
                cells = row.find_all('td')
                if len(cells) > 1:
                    ticker = cells[1].text.strip()
                    ticker = ticker.replace('.', '').replace('-', '')
                    if ticker:
                        tickers.append(ticker)
            
            logger.info(f"Fetched {len(tickers)} NASDAQ-100 tickers")
            return tickers
        except Exception as e:
            logger.error(f"Error fetching NASDAQ-100 tickers: {e}")
            return []
    
    def get_russell2000_tickers(self) -> List[str]:
        """Fetch Russell 2000 tickers from Wikipedia"""
        try:
            url = "https://en.wikipedia.org/wiki/Russell_2000"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Russell 2000 doesn't have a simple table, need to find alternative
            # For now, return empty list
            logger.warning("Russell 2000 ticker list not available from Wikipedia")
            return []
        except Exception as e:
            logger.error(f"Error fetching Russell 2000 tickers: {e}")
            return []
    
    def get_all_tickers(self) -> List[str]:
        """Get all tickers from multiple sources"""
        all_tickers = set()
        
        # Add S&P 500
        sp500 = self.get_sp500_tickers()
        all_tickers.update(sp500)
        
        # Add Russell 2000 (small caps)
        russell2000 = self.get_russell2000_tickers()
        all_tickers.update(russell2000)
        
        # Add Russell Midcap
        russell_midcap = self.get_russell_midcap_tickers()
        all_tickers.update(russell_midcap)
        
        # Add NASDAQ-100
        nasdaq100 = self.get_nasdaq100_tickers()
        all_tickers.update(nasdaq100)
        
        # Remove duplicates and return as list
        unique_tickers = list(all_tickers)
        logger.info(f"Total unique tickers from all sources: {len(unique_tickers)}")
        return unique_tickers
