import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from datetime import datetime, timedelta
import yfinance as yf
import logging
import asyncio
import random
from app.data.sources.multi_api_client import MultiAPIClient

logger = logging.getLogger(__name__)


class PolygonClient:
    def __init__(self):
        self.api_key = settings.polygon_api_key
        self.base_url_v2 = "https://api.polygon.io/v2"
        self.base_url_v3 = "https://api.polygon.io/v3"
        self.client = httpx.AsyncClient(timeout=30.0)
        # Use multi-API client for intraday data to distribute load
        self.multi_api = MultiAPIClient()
        # Rate limiting for yfinance calls
        self._last_yfinance_call = None
        self._yfinance_min_interval = 1.0  # Minimum 1 second between yfinance calls
        # Tickers that don't have intraday data available (ETFs, preferred stocks, etc.)
        self._intraday_excluded = {
            'AGMpF', 'AGMpG', 'AGMpH', 'FMCKM', 'FNMAS',  # Preferred stocks
            'PFF', 'PGX', 'PGF', 'PGJ', 'PGZ',  # Preferred ETFs
            'BND', 'BNDX', 'BSV', 'VCIT', 'VCSH',  # Bond ETFs
        }

    async def close(self):
        await self.client.aclose()

    async def get_daily_bars(
        self,
        symbol: str,
        timespan: str = "day",
        multiplier: int = 1,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get daily OHLCV data for a symbol"""
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"{self.base_url_v2}/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        params = {
            "apikey": self.api_key,
            "adjusted": "true",
            "sort": "desc",
            "limit": days
        }
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_intraday_bars(
        self,
        symbol: str,
        timespan: str = "minute",
        multiplier: int = 1,
        minutes: int = 60
    ) -> Dict[str, Any]:
        """Get intraday OHLCV data using multi-API client with fallback"""
        try:
            # Skip tickers that don't have intraday data
            if symbol.upper() in self._intraday_excluded:
                logger.debug(f"Skipping intraday fetch for excluded ticker {symbol}")
                return {"results": []}

            # Use multi-API client with fallback to distribute load
            data = await self.multi_api.get_intraday_bars(symbol, timespan, multiplier, minutes)

            if data and data.get("results"):
                return data
            else:
                logger.warning(f"No intraday data for {symbol} from any API")
                return {"results": []}

        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return {"results": []}

    async def get_stock_details(self, symbol: str) -> Dict[str, Any]:
        """Get stock details including sector, industry, market cap"""
        url = f"{self.base_url_v3}/reference/tickers/{symbol}"
        params = {"apikey": self.api_key}
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_tickers(
        self,
        market: str = "stocks",
        sector: Optional[str] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """Get list of tickers"""
        url = f"{self.base_url_v3}/reference/tickers"
        params = {
            "apikey": self.api_key,
            "market": market,
            "active": "true",
            "limit": limit
        }
        if sector:
            params["sector"] = sector
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()
