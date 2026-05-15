import httpx
from typing import Optional, Dict, Any
from app.core.config import settings
from datetime import datetime, timedelta
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


class PolygonClient:
    def __init__(self):
        self.api_key = settings.polygon_api_key
        self.base_url_v2 = "https://api.polygon.io/v2"
        self.base_url_v3 = "https://api.polygon.io/v3"
        self.client = httpx.AsyncClient(timeout=30.0)

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
        """Get intraday OHLCV data for a symbol (real-time using yfinance)"""
        try:
            # Use yfinance for real-time intraday data (free)
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            
            if data.empty:
                logger.warning(f"No intraday data for {symbol}")
                return {"results": []}
            
            # Get the most recent data point
            latest = data.iloc[-1]
            
            return {
                "results": [{
                    "t": int(latest.name.timestamp() * 1000),
                    "o": float(latest['Open']),
                    "h": float(latest['High']),
                    "l": float(latest['Low']),
                    "c": float(latest['Close']),
                    "v": int(latest['Volume']),
                    "vw": float(latest['Close'])  # Use close as VWAP approximation
                }]
            }
        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol} from yfinance: {e}")
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
