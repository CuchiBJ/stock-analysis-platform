"""
Universe Source Layer

Provider abstraction for multiple ticker sources:
- Polygon tickers endpoint
- NASDAQ listings
- NYSE listings
- ETFs universe
- IPO feeds
- Active listings
- Delisted listings
"""

import httpx
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TickerInfo:
    """Basic ticker information"""
    symbol: str
    name: str
    exchange: str
    asset_type: str = "common_stock"
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_active: bool = True
    listing_date: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "asset_type": self.asset_type,
            "market_cap": self.market_cap,
            "sector": self.sector,
            "industry": self.industry,
            "is_active": self.is_active,
            "listing_date": self.listing_date.isoformat() if self.listing_date else None
        }


@dataclass
class IPOInfo:
    """IPO information"""
    symbol: str
    company_name: str
    ipo_date: datetime
    exchange: str
    offering_price: Optional[float] = None
    shares_offered: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "ipo_date": self.ipo_date.isoformat(),
            "exchange": self.exchange,
            "offering_price": self.offering_price,
            "shares_offered": self.shares_offered
        }


@dataclass
class ETFInfo:
    """ETF information"""
    symbol: str
    name: str
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None
    underlying_index: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "expense_ratio": self.expense_ratio,
            "aum": self.aum,
            "underlying_index": self.underlying_index
        }


class UniverseSource(ABC):
    """Abstract interface for universe sources"""
    
    @abstractmethod
    async def get_active_listings(self, limit: int = 10000) -> List[TickerInfo]:
        """Get active listings from this source"""
        pass
    
    @abstractmethod
    async def get_delisted_listings(self, limit: int = 1000) -> List[TickerInfo]:
        """Get delisted listings from this source"""
        pass
    
    @abstractmethod
    async def get_ipo_feed(self, days: int = 30) -> List[IPOInfo]:
        """Get recent IPOs from this source"""
        pass
    
    @abstractmethod
    async def get_etf_universe(self) -> List[ETFInfo]:
        """Get ETF universe from this source"""
        pass


class PolygonSource(UniverseSource):
    """Polygon.io source for ticker data"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_active_listings(self, limit: int = 10000) -> List[TickerInfo]:
        """Get active listings from Polygon"""
        try:
            url = f"{self.base_url}/v3/reference/tickers"
            params = {
                "apikey": self.api_key,
                "market": "stocks",
                "active": "true",
                "limit": limit,
                "sort": "ticker"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            tickers = []
            if "results" in data:
                for ticker_data in data["results"]:
                    ticker = TickerInfo(
                        symbol=ticker_data.get("ticker", "").upper(),
                        name=ticker_data.get("name", ""),
                        exchange=ticker_data.get("primary_exchange", ""),
                        asset_type=self._determine_asset_type(ticker_data),
                        market_cap=ticker_data.get("market_cap"),
                        sector=ticker_data.get("sector"),
                        industry=ticker_data.get("industry"),
                        is_active=ticker_data.get("active", True)
                    )
                    tickers.append(ticker)
            
            logger.info(f"Polygon: Retrieved {len(tickers)} active listings")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching Polygon listings: {e}")
            return []
    
    async def get_delisted_listings(self, limit: int = 1000) -> List[TickerInfo]:
        """Get delisted listings from Polygon"""
        try:
            url = f"{self.base_url}/v3/reference/tickers"
            params = {
                "apikey": self.api_key,
                "market": "stocks",
                "active": "false",
                "limit": limit
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            tickers = []
            if "results" in data:
                for ticker_data in data["results"]:
                    ticker = TickerInfo(
                        symbol=ticker_data.get("ticker", "").upper(),
                        name=ticker_data.get("name", ""),
                        exchange=ticker_data.get("primary_exchange", ""),
                        asset_type=self._determine_asset_type(ticker_data),
                        market_cap=ticker_data.get("market_cap"),
                        is_active=False
                    )
                    tickers.append(ticker)
            
            logger.info(f"Polygon: Retrieved {len(tickers)} delisted listings")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching Polygon delistings: {e}")
            return []
    
    async def get_ipo_feed(self, days: int = 30) -> List[IPOInfo]:
        """Get recent IPOs from Polygon"""
        # Polygon doesn't have a dedicated IPO feed, return empty
        return []
    
    async def get_etf_universe(self) -> List[ETFInfo]:
        """Get ETF universe from Polygon"""
        try:
            url = f"{self.base_url}/v3/reference/tickers"
            params = {
                "apikey": self.api_key,
                "market": "stocks",
                "type": "ETF",
                "active": "true",
                "limit": 1000
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            etfs = []
            if "results" in data:
                for ticker_data in data["results"]:
                    etf = ETFInfo(
                        symbol=ticker_data.get("ticker", "").upper(),
                        name=ticker_data.get("name", ""),
                        aum=ticker_data.get("market_cap")
                    )
                    etfs.append(etf)
            
            logger.info(f"Polygon: Retrieved {len(etfs)} ETFs")
            return etfs
            
        except Exception as e:
            logger.error(f"Error fetching Polygon ETFs: {e}")
            return []
    
    def _determine_asset_type(self, ticker_data: Dict[str, Any]) -> str:
        """Determine asset type from ticker data"""
        ticker_type = ticker_data.get("type", "").lower()
        
        if ticker_type == "etf":
            return "etf"
        elif ticker_type == "adr":
            return "adr"
        elif ticker_type == "reit":
            return "reit"
        elif ticker_type == "preferred":
            return "preferred"
        else:
            return "common_stock"
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class NASDAQSource(UniverseSource):
    """NASDAQ source for ticker data"""
    
    def __init__(self):
        self.base_url = "https://api.nasdaq.com/api"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_active_listings(self, limit: int = 10000) -> List[TickerInfo]:
        """Get active NASDAQ listings"""
        try:
            # NASDAQ provides a CSV file of listed companies
            url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
            response = await self.client.get(url)
            response.raise_for_status()
            
            tickers = []
            lines = response.text.split('\n')
            
            for line in lines[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split('|')
                if len(parts) >= 2:
                    ticker = TickerInfo(
                        symbol=parts[0].upper(),
                        name=parts[1] if len(parts) > 1 else "",
                        exchange="NASDAQ",
                        is_active=True
                    )
                    tickers.append(ticker)
                
                if len(tickers) >= limit:
                    break
            
            logger.info(f"NASDAQ: Retrieved {len(tickers)} active listings")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching NASDAQ listings: {e}")
            return []
    
    async def get_delisted_listings(self, limit: int = 1000) -> List[TickerInfo]:
        """Get delisted NASDAQ listings"""
        try:
            url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqtraded.txt"
            response = await self.client.get(url)
            response.raise_for_status()
            
            tickers = []
            lines = response.text.split('\n')
            
            for line in lines[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split('|')
                if len(parts) >= 2:
                    ticker = TickerInfo(
                        symbol=parts[0].upper(),
                        name=parts[1] if len(parts) > 1 else "",
                        exchange="NASDAQ",
                        is_active=False
                    )
                    tickers.append(ticker)
                
                if len(tickers) >= limit:
                    break
            
            logger.info(f"NASDAQ: Retrieved {len(tickers)} delisted listings")
            return tickers
            
        except Exception as e:
            logger.error(f"Error fetching NASDAQ delistings: {e}")
            return []
    
    async def get_ipo_feed(self, days: int = 30) -> List[IPOInfo]:
        """Get recent NASDAQ IPOs"""
        # NASDAQ doesn't provide a public API for IPOs
        return []
    
    async def get_etf_universe(self) -> List[ETFInfo]:
        """Get NASDAQ ETF universe"""
        # NASDAQ ETFs would need to be filtered from active listings
        return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class NYSESource(UniverseSource):
    """NYSE source for ticker data"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_active_listings(self, limit: int = 10000) -> List[TickerInfo]:
        """Get active NYSE listings"""
        try:
            # NYSE provides a CSV file of listed companies
            url = "https://www.nyse.com/api/nyse/tickers"
            response = await self.client.get(url)
            response.raise_for_status()
            
            # NYSE API may require authentication
            # For now, return empty and log
            logger.warning("NYSE API may require authentication")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching NYSE listings: {e}")
            return []
    
    async def get_delisted_listings(self, limit: int = 1000) -> List[TickerInfo]:
        """Get delisted NYSE listings"""
        return []
    
    async def get_ipo_feed(self, days: int = 30) -> List[IPOInfo]:
        """Get recent NYSE IPOs"""
        return []
    
    async def get_etf_universe(self) -> List[ETFInfo]:
        """Get NYSE ETF universe"""
        return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


class UniverseSourceManager:
    """
    Universe Source Manager
    
    Aggregates data from multiple sources:
    - Polygon (primary source)
    - NASDAQ (exchange-specific)
    - NYSE (exchange-specific)
    - ETFs universe
    - IPO feeds
    """
    
    def __init__(self, polygon_api_key: str):
        self.sources: List[UniverseSource] = [
            PolygonSource(polygon_api_key),
            NASDAQSource(),
            NYSESource()
        ]
    
    async def get_all_active_listings(self, limit: int = 10000) -> List[TickerInfo]:
        """
        Get active listings from all sources.
        
        Args:
            limit: Maximum number of listings to return per source
            
        Returns:
            Combined list of active listings from all sources
        """
        all_tickers = []
        
        for source in self.sources:
            tickers = await source.get_active_listings(limit)
            all_tickers.extend(tickers)
        
        # Deduplicate by symbol
        seen_symbols = set()
        unique_tickers = []
        
        for ticker in all_tickers:
            if ticker.symbol not in seen_symbols:
                seen_symbols.add(ticker.symbol)
                unique_tickers.append(ticker)
        
        logger.info(f"Total unique active listings: {len(unique_tickers)}")
        return unique_tickers
    
    async def get_all_delisted_listings(self, limit: int = 1000) -> List[TickerInfo]:
        """
        Get delisted listings from all sources.
        
        Args:
            limit: Maximum number of listings to return per source
            
        Returns:
            Combined list of delisted listings from all sources
        """
        all_tickers = []
        
        for source in self.sources:
            tickers = await source.get_delisted_listings(limit)
            all_tickers.extend(tickers)
        
        # Deduplicate by symbol
        seen_symbols = set()
        unique_tickers = []
        
        for ticker in all_tickers:
            if ticker.symbol not in seen_symbols:
                seen_symbols.add(ticker.symbol)
                unique_tickers.append(ticker)
        
        logger.info(f"Total unique delisted listings: {len(unique_tickers)}")
        return unique_tickers
    
    async def get_all_ipo_feed(self, days: int = 30) -> List[IPOInfo]:
        """
        Get IPO feed from all sources.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Combined list of IPOs from all sources
        """
        all_ipos = []
        
        for source in self.sources:
            ipos = await source.get_ipo_feed(days)
            all_ipos.extend(ipos)
        
        logger.info(f"Total IPOs: {len(all_ipos)}")
        return all_ipos
    
    async def get_all_etf_universe(self) -> List[ETFInfo]:
        """
        Get ETF universe from all sources.
        
        Returns:
            Combined list of ETFs from all sources
        """
        all_etfs = []
        
        for source in self.sources:
            etfs = await source.get_etf_universe()
            all_etfs.extend(etfs)
        
        # Deduplicate by symbol
        seen_symbols = set()
        unique_etfs = []
        
        for etf in all_etfs:
            if etf.symbol not in seen_symbols:
                seen_symbols.add(etf.symbol)
                unique_etfs.append(etf)
        
        logger.info(f"Total unique ETFs: {len(unique_etfs)}")
        return unique_etfs
    
    async def close_all(self):
        """Close all source connections"""
        for source in self.sources:
            await source.close()
