"""Multi-API client for intraday data with fallback to distribute load"""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import asyncio
import random

logger = logging.getLogger(__name__)


class MultiAPIClient:
    """
    Multi-API client for intraday data with fallback to distribute load across providers.
    Uses Finnhub, Alpha Vantage, and Polygon as fallbacks.
    """
    
    def __init__(self):
        # API keys (should be in config)
        self.finnhub_api_key = "YOUR_FINNHUB_KEY"  # Get from config
        self.alpha_vantage_key = "YOUR_ALPHA_VANTAGE_KEY"  # Get from config
        self.polygon_api_key = "YOUR_POLYGON_KEY"  # Get from config
        
        # Clients
        self.finnhub_client = httpx.AsyncClient(timeout=30.0)
        self.polygon_client = httpx.AsyncClient(timeout=30.0)
        self.alpha_vantage_client = httpx.AsyncClient(timeout=30.0)
        
        # Rate limiting per API
        self._last_finnhub_call = None
        self._last_polygon_call = None
        self._last_alpha_vantage_call = None
        
        self._finnhub_interval = 0.5  # 2 requests/second
        self._polygon_interval = 0.5  # 2 requests/second
        self._alpha_vantage_interval = 1.0  # 1 request/second
    
    async def close(self):
        """Close all clients"""
        await self.finnhub_client.aclose()
        await self.polygon_client.aclose()
        await self.alpha_vantage_client.aclose()
    
    async def _wait_for_rate_limit(self, provider: str):
        """Wait based on provider's rate limit"""
        now = datetime.utcnow()
        
        if provider == "finnhub" and self._last_finnhub_call:
            elapsed = (now - self._last_finnhub_call).total_seconds()
            if elapsed < self._finnhub_interval:
                await asyncio.sleep(self._finnhub_interval - elapsed)
            self._last_finnhub_call = datetime.utcnow()
        
        elif provider == "polygon" and self._last_polygon_call:
            elapsed = (now - self._last_polygon_call).total_seconds()
            if elapsed < self._polygon_interval:
                await asyncio.sleep(self._polygon_interval - elapsed)
            self._last_polygon_call = datetime.utcnow()
        
        elif provider == "alpha_vantage" and self._last_alpha_vantage_call:
            elapsed = (now - self._last_alpha_vantage_call).total_seconds()
            if elapsed < self._alpha_vantage_interval:
                await asyncio.sleep(self._alpha_vantage_interval - elapsed)
            self._last_alpha_vantage_call = datetime.utcnow()
    
    async def _get_from_finnhub(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Try to get intraday data from Finnhub"""
        try:
            await self._wait_for_rate_limit("finnhub")
            
            # Finnhub API for intraday data
            url = f"https://finnhub.io/api/v1/stock/candle"
            params = {
                "symbol": symbol,
                "resolution": "1",
                "from": int((datetime.utcnow() - timedelta(days=1)).timestamp()),
                "to": int(datetime.utcnow().timestamp()),
                "token": self.finnhub_api_key
            }
            
            response = await self.finnhub_client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("s") == "ok" and data.get("c"):
                    # Convert to our format
                    latest = data
                    return {
                        "results": [{
                            "t": int(latest["t"][-1] * 1000),
                            "o": float(latest["o"][-1]),
                            "h": float(latest["h"][-1]),
                            "l": float(latest["l"][-1]),
                            "c": float(latest["c"][-1]),
                            "v": int(latest["v"][-1]),
                            "vw": float(latest["c"][-1])  # Use close as VWAP
                        }]
                    }
            return None
        except Exception as e:
            logger.warning(f"Finnhub error for {symbol}: {e}")
            return None
    
    async def _get_from_polygon(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Try to get intraday data from Polygon"""
        try:
            await self._wait_for_rate_limit("polygon")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(minutes=60)
            
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            params = {
                "apikey": self.polygon_api_key,
                "adjusted": "true",
                "sort": "desc",
                "limit": 500
            }
            
            response = await self.polygon_client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if "results" in data and data["results"]:
                    return data
            return None
        except Exception as e:
            logger.warning(f"Polygon error for {symbol}: {e}")
            return None
    
    async def _get_from_alpha_vantage(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Try to get intraday data from Alpha Vantage"""
        try:
            await self._wait_for_rate_limit("alpha_vantage")
            
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": "1min",
                "apikey": self.alpha_vantage_key,
                "outputsize": "compact"
            }
            
            response = await self.alpha_vantage_client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if "Time Series (1min)" in data:
                    time_series = data["Time Series (1min)"]
                    latest_time = list(time_series.keys())[0]
                    latest = time_series[latest_time]
                    
                    return {
                        "results": [{
                            "t": int(datetime.strptime(latest_time, "%Y-%m-%d %H:%M:%S").timestamp() * 1000),
                            "o": float(latest["1. open"]),
                            "h": float(latest["2. high"]),
                            "l": float(latest["3. low"]),
                            "c": float(latest["4. close"]),
                            "v": int(latest["5. volume"]),
                            "vw": float(latest["4. close"])
                        }]
                    }
            return None
        except Exception as e:
            logger.warning(f"Alpha Vantage error for {symbol}: {e}")
            return None
    
    async def get_intraday_bars(
        self,
        symbol: str,
        timespan: str = "minute",
        multiplier: int = 1,
        minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get intraday OHLCV data with fallback across multiple APIs.
        Tries providers in order: Finnhub -> Polygon -> Alpha Vantage
        """
        providers = ["finnhub", "polygon", "alpha_vantage"]
        
        for provider in providers:
            try:
                if provider == "finnhub":
                    data = await self._get_from_finnhub(symbol)
                elif provider == "polygon":
                    data = await self._get_from_polygon(symbol)
                elif provider == "alpha_vantage":
                    data = await self._get_from_alpha_vantage(symbol)
                
                if data and data.get("results"):
                    logger.debug(f"Got intraday data for {symbol} from {provider}")
                    return data
                
            except Exception as e:
                logger.warning(f"Error getting intraday data for {symbol} from {provider}: {e}")
                continue
        
        logger.warning(f"Failed to get intraday data for {symbol} from all providers")
        return {"results": []}
