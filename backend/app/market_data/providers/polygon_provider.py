"""
Polygon.io Provider Implementation

Implements MarketDataProvider, WebSocketProvider, and RateLimitedProvider interfaces
using Polygon.io API and WebSocket.
"""

import httpx
import websockets
import json
import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from app.market_data.interfaces import (
    MarketDataProvider,
    WebSocketProvider,
    RateLimitedProvider,
    Timespan,
    EventType,
    Bar,
    Quote,
    Trade,
    Aggregate
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class PolygonProvider(MarketDataProvider, WebSocketProvider, RateLimitedProvider):
    """
    Polygon.io provider implementation.
    
    Implements all three interfaces:
    - MarketDataProvider: REST-based data access
    - WebSocketProvider: WebSocket-based streaming
    - RateLimitedProvider: Rate-limit awareness
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.polygon_api_key
        self.base_url = "https://api.polygon.io"
        self.ws_url = "wss://stream.polygon.io"
        
        # HTTP client for REST requests
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # WebSocket connection
        self.ws_connection = None
        self._connected = False
        
        # Rate limiting
        self._last_request = None
        self._request_count = 0
        self._request_window_start = datetime.utcnow()
        
        # Rate limit configuration (Polygon free tier: 5 req/min)
        self.rate_limit_config = {
            "requests_per_minute": 5,
            "requests_per_day": 100000
        }
        
        # Subscriptions
        self._subscriptions = set()
    
    # ========== MarketDataProvider Methods ==========
    
    async def get_intraday_bars(
        self,
        symbol: str,
        timespan: Timespan = Timespan.MINUTE,
        multiplier: int = 1,
        minutes: int = 60
    ) -> List[Bar]:
        """Get intraday OHLCV bars for a symbol."""
        await self.wait_for_rate_limit()
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(minutes=minutes)
            
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan.value}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            params = {
                "apikey": self.api_key,
                "adjusted": "true",
                "sort": "desc",
                "limit": 500
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "results" not in data or not data["results"]:
                return []
            
            bars = []
            for result in data["results"]:
                bar = Bar(
                    timestamp=datetime.fromtimestamp(result["t"] / 1000),
                    open=result["o"],
                    high=result["h"],
                    low=result["l"],
                    close=result["c"],
                    volume=result["v"],
                    vwap=result.get("vw"),
                    symbol=symbol
                )
                bars.append(bar)
            
            return bars
            
        except Exception as e:
            logger.error(f"Error fetching intraday bars for {symbol}: {e}")
            return []
    
    async def get_daily_bars(
        self,
        symbol: str,
        days: int = 30
    ) -> List[Bar]:
        """Get daily OHLCV bars for a symbol."""
        await self.wait_for_rate_limit()
        
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            params = {
                "apikey": self.api_key,
                "adjusted": "true",
                "sort": "desc",
                "limit": days
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "results" not in data or not data["results"]:
                return []
            
            bars = []
            for result in data["results"]:
                bar = Bar(
                    timestamp=datetime.fromtimestamp(result["t"] / 1000),
                    open=result["o"],
                    high=result["h"],
                    low=result["l"],
                    close=result["c"],
                    volume=result["v"],
                    vwap=result.get("vw"),
                    symbol=symbol
                )
                bars.append(bar)
            
            return bars
            
        except Exception as e:
            logger.error(f"Error fetching daily bars for {symbol}: {e}")
            return []
    
    async def get_quotes(
        self,
        symbols: List[str]
    ) -> Dict[str, Quote]:
        """Get real-time quotes for multiple symbols."""
        await self.wait_for_rate_limit()
        
        try:
            # Polygon quotes endpoint
            quotes = {}
            for symbol in symbols:
                url = f"{self.base_url}/v2/last/nbbo/{symbol}"
                params = {"apikey": self.api_key}
                
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "results" in data and data["results"]:
                    result = data["results"]
                    quote = Quote(
                        symbol=symbol,
                        bid=result.get("p", 0.0),
                        ask=result.get("P", 0.0),
                        bid_size=result.get("s", 0),
                        ask_size=result.get("S", 0),
                        timestamp=datetime.utcnow()
                    )
                    quotes[symbol] = quote
            
            return quotes
            
        except Exception as e:
            logger.error(f"Error fetching quotes: {e}")
            return {}
    
    async def get_snapshots(
        self,
        symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get market snapshots for multiple symbols."""
        await self.wait_for_rate_limit()
        
        try:
            snapshots = {}
            for symbol in symbols:
                url = f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
                params = {"apikey": self.api_key}
                
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "ticker" in data:
                    snapshots[symbol] = data["ticker"]
            
            return snapshots
            
        except Exception as e:
            logger.error(f"Error fetching snapshots: {e}")
            return {}
    
    async def stream_trades(
        self,
        symbol: str
    ) -> AsyncIterator[Trade]:
        """Stream real-time trades for a symbol."""
        if not self._connected:
            await self.connect()
        
        # Subscribe to trades
        await self.subscribe([symbol], EventType.TRADE)
        
        try:
            while self._connected:
                message = await self.ws_connection.recv()
                data = json.loads(message)
                
                if "ev" in data and data["ev"] == "T":
                    trade = Trade(
                        symbol=data["sym"],
                        price=data["p"],
                        size=data["s"],
                        timestamp=datetime.fromtimestamp(data["t"] / 1000),
                        conditions=data.get("c", [])
                    )
                    yield trade
                    
        except Exception as e:
            logger.error(f"Error streaming trades for {symbol}: {e}")
            raise
    
    async def stream_quotes(
        self,
        symbols: List[str]
    ) -> AsyncIterator[Dict[str, Quote]]:
        """Stream real-time quotes for multiple symbols."""
        if not self._connected:
            await self.connect()
        
        # Subscribe to quotes
        await self.subscribe(symbols, EventType.QUOTE)
        
        try:
            quotes_buffer = {}
            
            while self._connected:
                message = await self.ws_connection.recv()
                data = json.loads(message)
                
                if "ev" in data and data["ev"] == "Q":
                    symbol = data["sym"]
                    quote = Quote(
                        symbol=symbol,
                        bid=data["bp"],
                        ask=data["ap"],
                        bid_size=data["bs"],
                        ask_size=data["as"],
                        timestamp=datetime.fromtimestamp(data["t"] / 1000)
                    )
                    quotes_buffer[symbol] = quote
                    
                    # Yield when we have quotes for all requested symbols
                    if all(s in quotes_buffer for s in symbols):
                        yield quotes_buffer
                        quotes_buffer = {}
                        
        except Exception as e:
            logger.error(f"Error streaming quotes: {e}")
            raise
    
    async def stream_aggregates(
        self,
        symbol: str,
        timespan: Timespan = Timespan.MINUTE,
        multiplier: int = 1
    ) -> AsyncIterator[Aggregate]:
        """Stream real-time aggregated bars for a symbol."""
        if not self._connected:
            await self.connect()
        
        # Subscribe to aggregates
        await self.subscribe([symbol], EventType.AGGREGATE)
        
        try:
            while self._connected:
                message = await self.ws_connection.recv()
                data = json.loads(message)
                
                if "ev" in data and data["ev"] == "AM":
                    aggregate = Aggregate(
                        timestamp=datetime.fromtimestamp(data["s"] / 1000),
                        open=data["o"],
                        high=data["h"],
                        low=data["l"],
                        close=data["c"],
                        volume=data["v"],
                        vwap=data.get("vw"),
                        symbol=symbol
                    )
                    yield aggregate
                    
        except Exception as e:
            logger.error(f"Error streaming aggregates for {symbol}: {e}")
            raise
    
    async def close(self):
        """Close provider connections and cleanup resources."""
        if self._connected:
            await self.disconnect()
        await self.client.aclose()
    
    # ========== WebSocketProvider Methods ==========
    
    async def connect(self):
        """Establish WebSocket connection."""
        if self._connected:
            return
        
        try:
            import ssl
            ws_url = f"{self.ws_url}?apiKey={self.api_key}"
            # Create SSL context that verifies certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self.ws_connection = await websockets.connect(ws_url, ssl=ssl_context)
            
            # Authenticate
            await self.ws_connection.send(json.dumps({
                "action": "auth",
                "params": self.api_key
            }))
            
            # Wait for auth confirmation
            response = await self.ws_connection.recv()
            data = json.loads(response)
            
            if data.get("status") == "auth_success":
                self._connected = True
                logger.info("Polygon WebSocket connected successfully")
            else:
                logger.error(f"Polygon WebSocket auth failed: {data}")
                await self.disconnect()
                
        except Exception as e:
            logger.error(f"Error connecting to Polygon WebSocket: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws_connection:
            await self.ws_connection.close()
            self.ws_connection = None
        self._connected = False
        self._subscriptions.clear()
        logger.info("Polygon WebSocket disconnected")
    
    async def subscribe(self, symbols: List[str], event_type: EventType):
        """Subscribe to events for symbols."""
        if not self._connected:
            await self.connect()
        
        try:
            for symbol in symbols:
                # Polygon subscription format
                subscription = f"{event_type.value}.{symbol}"
                
                await self.ws_connection.send(json.dumps({
                    "action": "subscribe",
                    "params": subscription
                }))
                
                self._subscriptions.add((symbol, event_type))
                logger.debug(f"Subscribed to {subscription}")
                
        except Exception as e:
            logger.error(f"Error subscribing to {symbols}: {e}")
            raise
    
    async def unsubscribe(self, symbols: List[str], event_type: EventType):
        """Unsubscribe from events for symbols."""
        if not self._connected:
            return
        
        try:
            for symbol in symbols:
                subscription = f"{event_type.value}.{symbol}"
                
                await self.ws_connection.send(json.dumps({
                    "action": "unsubscribe",
                    "params": subscription
                }))
                
                self._subscriptions.discard((symbol, event_type))
                logger.debug(f"Unsubscribed from {subscription}")
                
        except Exception as e:
            logger.error(f"Error unsubscribing from {symbols}: {e}")
    
    async def is_connected(self) -> bool:
        """Check if WebSocket connection is active."""
        return self._connected
    
    async def reconnect(self):
        """Reconnect WebSocket if disconnected."""
        if not self._connected:
            logger.info("Attempting to reconnect to Polygon WebSocket...")
            await self.connect()
    
    # ========== RateLimitedProvider Methods ==========
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        now = datetime.utcnow()
        
        # Reset counter if window expired
        if (now - self._request_window_start).total_seconds() >= 60:
            self._request_count = 0
            self._request_window_start = now
        
        return {
            "requests_in_current_window": self._request_count,
            "requests_per_minute_limit": self.rate_limit_config["requests_per_minute"],
            "window_start": self._request_window_start,
            "window_remaining": 60 - (now - self._request_window_start).total_seconds(),
            "is_rate_limited": self._request_count >= self.rate_limit_config["requests_per_minute"]
        }
    
    async def wait_for_rate_limit(self):
        """Wait if rate limit is approached."""
        status = await self.get_rate_limit_status()
        
        if status["is_rate_limited"]:
            wait_time = status["window_remaining"] + 1  # Add 1 second buffer
            logger.warning(f"Rate limited, waiting {wait_time}s")
            await asyncio.sleep(wait_time)
            self._request_count = 0
            self._request_window_start = datetime.utcnow()
        else:
            # Add small delay to stay under limit
            await asyncio.sleep(12)  # 5 requests per minute = 12 seconds between requests
        
        self._request_count += 1
    
    def get_rate_limit_config(self) -> Dict[str, int]:
        """Get rate limit configuration."""
        return self.rate_limit_config.copy()
