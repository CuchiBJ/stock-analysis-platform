"""
Market Data Abstraction Layer

Provider-agnostic interfaces for market data.
Allows switching providers without breaking the system.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class Timespan(Enum):
    """Time span for data aggregation"""
    MINUTE = "minute"
    MINUTE_5 = "minute"
    MINUTE_15 = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class EventType(Enum):
    """Types of market events"""
    TRADE = "trade"
    QUOTE = "quote"
    AGGREGATE = "aggregate"
    BAR = "bar"


@dataclass
class Bar:
    """OHLCV bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    symbol: Optional[str] = None


@dataclass
class Quote:
    """Real-time quote data"""
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp: datetime


@dataclass
class Trade:
    """Individual trade data"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    conditions: Optional[List[str]] = None


@dataclass
class Aggregate:
    """Aggregated bar data (Polygon format)"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    symbol: Optional[str] = None


class MarketDataProvider(ABC):
    """
    Abstract interface for market data providers.
    
    All providers must implement these methods to ensure
    provider-agnostic operation.
    """
    
    @abstractmethod
    async def get_intraday_bars(
        self,
        symbol: str,
        timespan: Timespan = Timespan.MINUTE,
        multiplier: int = 1,
        minutes: int = 60
    ) -> List[Bar]:
        """
        Get intraday OHLCV bars for a symbol.
        
        Args:
            symbol: Ticker symbol
            timespan: Time aggregation (minute, hour, etc.)
            multiplier: Multiplier for timespan (e.g., 5 for 5-minute)
            minutes: Number of minutes of data to fetch
            
        Returns:
            List of Bar objects
        """
        pass
    
    @abstractmethod
    async def get_daily_bars(
        self,
        symbol: str,
        days: int = 30
    ) -> List[Bar]:
        """
        Get daily OHLCV bars for a symbol.
        
        Args:
            symbol: Ticker symbol
            days: Number of days of data to fetch
            
        Returns:
            List of Bar objects
        """
        pass
    
    @abstractmethod
    async def get_quotes(
        self,
        symbols: List[str]
    ) -> Dict[str, Quote]:
        """
        Get real-time quotes for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbol to Quote
        """
        pass
    
    @abstractmethod
    async def get_snapshots(
        self,
        symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get market snapshots for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbol to snapshot data
        """
        pass
    
    @abstractmethod
    async def stream_trades(
        self,
        symbol: str
    ) -> AsyncIterator[Trade]:
        """
        Stream real-time trades for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Yields:
            Trade objects as they occur
        """
        pass
    
    @abstractmethod
    async def stream_quotes(
        self,
        symbols: List[str]
    ) -> AsyncIterator[Dict[str, Quote]]:
        """
        Stream real-time quotes for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            
        Yields:
            Dictionary mapping symbol to Quote
        """
        pass
    
    @abstractmethod
    async def stream_aggregates(
        self,
        symbol: str,
        timespan: Timespan = Timespan.MINUTE,
        multiplier: int = 1
    ) -> AsyncIterator[Aggregate]:
        """
        Stream real-time aggregated bars for a symbol.
        
        Args:
            symbol: Ticker symbol
            timespan: Time aggregation
            multiplier: Multiplier for timespan
            
        Yields:
            Aggregate objects as they complete
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close provider connections and cleanup resources."""
        pass


class WebSocketProvider(ABC):
    """
    Abstract interface for WebSocket-based market data providers.
    
    WebSocket providers maintain persistent connections for real-time streaming.
    """
    
    @abstractmethod
    async def connect(self):
        """Establish WebSocket connection."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close WebSocket connection."""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str], event_type: EventType):
        """
        Subscribe to events for symbols.
        
        Args:
            symbols: List of ticker symbols
            event_type: Type of events to subscribe to
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, symbols: List[str], event_type: EventType):
        """
        Unsubscribe from events for symbols.
        
        Args:
            symbols: List of ticker symbols
            event_type: Type of events to unsubscribe from
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if WebSocket connection is active."""
        pass
    
    @abstractmethod
    async def reconnect(self):
        """Reconnect WebSocket if disconnected."""
        pass


class RateLimitedProvider(ABC):
    """
    Abstract interface for rate-limit aware providers.
    
    Providers implementing this interface are rate-limit aware
    and handle rate limiting gracefully.
    """
    
    @abstractmethod
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        pass
    
    @abstractmethod
    async def wait_for_rate_limit(self):
        """Wait if rate limit is approached."""
        pass
    
    @abstractmethod
    def get_rate_limit_config(self) -> Dict[str, int]:
        """
        Get rate limit configuration.
        
        Returns:
            Dictionary with rate limit settings
        """
        pass
