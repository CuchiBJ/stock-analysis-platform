from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.sql import text
from typing import List, Dict, Any, Optional
from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.sector_mapping import map_sector_to_tradingview
import logging
from app.schemas.scanner import ScannerFilter
from app.data.processors.breakout import detect_consolidation, detect_squeeze, detect_near_high
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class QuickScannerFilter:
    """Quick scanner filter for preset-based scanning"""
    min_rvol: Optional[float] = None
    min_relative_volume: Optional[float] = None
    market_cap_range: Optional[tuple[float, float]] = None
    price_range: Optional[tuple[float, float]] = None
    sector: Optional[str] = None
    min_distance_high: Optional[float] = None
    min_distance_high_52w: Optional[float] = None
    max_distance_high_52w: Optional[float] = None
    min_distance_ema20: Optional[float] = None
    min_rs: Optional[float] = None
    min_volume: Optional[float] = None
    max_adr: Optional[float] = None
    gap_pct_range: Optional[tuple[float, float]] = None
    consolidation_days: Optional[int] = None
    upcoming_earnings_days: Optional[int] = None
    has_earnings: Optional[bool] = None
    max_bollinger_width: Optional[float] = None
    ema20_above_ema50: Optional[bool] = None
    ema50_above_ema200: Optional[bool] = None
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ScannerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_scan(self, filter: ScannerFilter) -> List[dict]:
        """Run scanner with given filters"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(Stock.is_active == True)
        
        # Apply filters
        conditions = []
        
        if filter.min_relative_volume:
            conditions.append(
                StockMetrics.relative_volume >= filter.min_relative_volume
            )
        
        if filter.max_distance_to_ema20 is not None:
            conditions.append(
                StockMetrics.distance_to_ema20 <= filter.max_distance_to_ema20
            )
        
        if filter.min_distance_to_ema50 is not None:
            conditions.append(
                StockMetrics.distance_to_ema50 >= filter.min_distance_to_ema50
            )
        
        if filter.sector:
            conditions.append(Stock.sector == filter.sector)
        
        if filter.industry:
            conditions.append(Stock.industry == filter.industry)
        
        if filter.min_market_cap:
            conditions.append(Stock.market_cap >= filter.min_market_cap)
        
        if filter.max_market_cap:
            conditions.append(Stock.market_cap <= filter.max_market_cap)
        
        if filter.is_adr is not None:
            conditions.append(Stock.is_adr == filter.is_adr)
        
        # Price range filters (using EMA20 as proxy)
        if filter.min_price:
            conditions.append(StockMetrics.ema20 >= filter.min_price)
        
        if filter.max_price:
            conditions.append(StockMetrics.ema20 <= filter.max_price)
        
        # Breakout filter
        if filter.breakout:
            conditions.append(
                and_(
                    StockMetrics.relative_volume >= 2.0,
                    StockMetrics.distance_to_ema20 > 0,
                    StockMetrics.distance_to_ema20 < 5
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Limit results for performance
        query = query.limit(500)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        results = []
        for stock, metrics in rows:
            results.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "industry": stock.industry,
                "market_cap": stock.market_cap,
                "price": metrics.ema20,  # Using EMA20 as proxy for current price
                "relative_volume": metrics.relative_volume,
                "distance_to_ema20": metrics.distance_to_ema20,
                "distance_to_ema50": metrics.distance_to_ema50,
                "rsi": metrics.rsi,
                "is_adr": stock.is_adr
            })
        
        logger.info(f"Scan returned {len(results)} results")
        return results

    async def get_breakout_stocks(self, limit: int = 50) -> List[dict]:
        """Get stocks breaking out with high volume"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                StockMetrics.relative_volume >= 2.0,
                StockMetrics.distance_to_ema20 > 0,
                StockMetrics.distance_to_ema20 < 5,
                StockMetrics.rsi < 70  # Not overbought
            )
        ).order_by(StockMetrics.relative_volume.desc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "price": metrics.ema20,
                "relative_volume": metrics.relative_volume,
                "distance_to_ema20": metrics.distance_to_ema20,
                "rsi": metrics.rsi
            }
            for stock, metrics in rows
        ]

    async def get_consolidating_stocks(self, limit: int = 50) -> List[dict]:
        """Get stocks in consolidation (tight range)"""
        # This requires price history analysis
        # For MVP, use metrics as proxy: low RVOL + near EMAs
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                StockMetrics.relative_volume < 1.0,
                func.abs(StockMetrics.distance_to_ema20) < 2,
                StockMetrics.rsi.between(40, 60)  # Neutral RSI
            )
        ).order_by(Stock.market_cap.desc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "market_cap": stock.market_cap,
                "price": metrics.ema20,
                "relative_volume": metrics.relative_volume,
                "distance_to_ema20": metrics.distance_to_ema20,
                "rsi": metrics.rsi
            }
            for stock, metrics in rows
        ]

    async def get_near_high_stocks(self, threshold: float = 5.0, limit: int = 50) -> List[dict]:
        """Get stocks near 52-week high"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                StockMetrics.distance_to_high_52w is not None,
                StockMetrics.distance_to_high_52w >= 0,
                StockMetrics.distance_to_high_52w <= threshold,
                StockMetrics.relative_volume >= 1.5
            )
        ).order_by(StockMetrics.distance_to_high_52w.asc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "price": metrics.ema20,
                "distance_to_high_52w": metrics.distance_to_high_52w,
                "relative_volume": metrics.relative_volume,
                "rsi": metrics.rsi
            }
            for stock, metrics in rows
        ]

    async def get_momentum_leaders(self, limit: int = 50) -> List[dict]:
        """Get momentum leaders (strong uptrend)"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                StockMetrics.ema20 > StockMetrics.ema50,
                StockMetrics.ema50 > StockMetrics.ema200,
                StockMetrics.distance_to_ema20 > 0,
                StockMetrics.distance_to_ema20 < 10,
                StockMetrics.rsi > 50,
                StockMetrics.rsi < 80
            )
        ).order_by(StockMetrics.distance_to_ema20.desc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "price": metrics.ema20,
                "ema20": metrics.ema20,
                "ema50": metrics.ema50,
                "ema200": metrics.ema200,
                "distance_to_ema20": metrics.distance_to_ema20,
                "rsi": metrics.rsi
            }
            for stock, metrics in rows
        ]

    async def get_oversold_stocks(self, limit: int = 50) -> List[dict]:
        """Get oversold stocks for potential bounce"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                StockMetrics.rsi < 30,
                StockMetrics.distance_to_ema20 < -5,
                StockMetrics.relative_volume >= 1.0
            )
        ).order_by(StockMetrics.rsi.asc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "price": metrics.ema20,
                "distance_to_ema20": metrics.distance_to_ema20,
                "rsi": metrics.rsi,
                "relative_volume": metrics.relative_volume
            }
            for stock, metrics in rows
        ]

    async def get_custom_screener_stocks(self, limit: int = 50) -> List[dict]:
        """Custom screener based on user's criteria:
        - Precio > SMA 50
        - Market cap 600M - 200B
        - Perf 1Y > 30%
        - SMA 150 > SMA 200
        - Precio > SMA 150
        - Vol medio 10d > 1M
        - SMA 50 > SMA 150
        - 52W range > 60% (high - low) / low > 0.6
        - Precio > 10 USD
        - Perf 1W < 0%
        - Precio > 52W low by 70% (price - low) / low > 0.7
        """
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(
            and_(
                Stock.is_active == True,
                # Precio > SMA 50
                StockMetrics.current_price > StockMetrics.sma50,
                # Market cap 600M - 200B
                Stock.market_cap >= 600000000,
                Stock.market_cap <= 200000000000,
                # Perf 1Y > 30%
                StockMetrics.perf_1y > 30,
                # SMA 150 > SMA 200
                StockMetrics.sma150 > StockMetrics.sma200,
                # Precio > SMA 150
                StockMetrics.current_price > StockMetrics.sma150,
                # Vol medio 10d > 1M
                StockMetrics.avg_volume_10d > 1000000,
                # SMA 50 > SMA 150
                StockMetrics.sma50 > StockMetrics.sma150,
                # Precio > 10 USD
                StockMetrics.current_price > 10,
                # Perf 1W < 0%
                StockMetrics.perf_1w < 0
            )
        ).order_by(StockMetrics.perf_1y.desc()).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        results = []
        for stock, metrics in rows:
            # Calculate 52W range percentage
            if metrics.low_52w and metrics.low_52w > 0:
                range_52w = ((metrics.distance_to_high_52w / 100 + 1) * metrics.current_price - metrics.low_52w) / metrics.low_52w
            else:
                range_52w = 0
            
            # Calculate price above 52W low percentage
            if metrics.low_52w and metrics.low_52w > 0:
                above_low_52w = (metrics.current_price - metrics.low_52w) / metrics.low_52w
            else:
                above_low_52w = 0
            
            # Filter by 52W range > 60% and price > 52W low by 70%
            if range_52w > 0.6 and above_low_52w > 0.7:
                results.append({
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "sector": map_sector_to_tradingview(stock.sector),
                    "industry": stock.industry,
                    "market_cap": stock.market_cap,
                    "price": metrics.current_price,
                    "sma50": metrics.sma50,
                    "sma150": metrics.sma150,
                    "sma200": metrics.sma200,
                    "perf_1y": metrics.perf_1y,
                    "perf_1w": metrics.perf_1w,
                    "avg_volume_10d": metrics.avg_volume_10d,
                    "low_52w": metrics.low_52w,
                    "range_52w": range_52w,
                    "above_low_52w": above_low_52w
                })
        
        logger.info(f"Custom screener returned {len(results)} results")
        return results

    async def run_quick_scan(self, filter: Dict[str, Any], limit: int = 50) -> List[dict]:
        """Run quick scan with preset filters"""
        query = select(Stock, StockMetrics).join(
            StockMetrics, Stock.symbol == StockMetrics.symbol
        ).where(Stock.is_active == True)
        
        conditions = []
        
        # RVOL filter
        if filter.get('min_relative_volume') or filter.get('min_rvol'):
            min_rvol = filter.get('min_relative_volume') or filter.get('min_rvol')
            conditions.append(StockMetrics.relative_volume >= min_rvol)
        
        # Market cap range
        if filter.get('market_cap_range'):
            min_mc, max_mc = filter['market_cap_range']
            conditions.append(Stock.market_cap >= min_mc)
            conditions.append(Stock.market_cap <= max_mc)
        
        # Price range
        if filter.get('price_range'):
            min_price, max_price = filter['price_range']
            conditions.append(StockMetrics.current_price >= min_price)
            conditions.append(StockMetrics.current_price <= max_price)
        
        # Sector filter
        if filter.get('sector'):
            conditions.append(Stock.sector == filter['sector'])
        
        # Distance to high filters
        if filter.get('min_distance_high_52w'):
            conditions.append(StockMetrics.distance_to_high_52w >= filter['min_distance_high_52w'])
        
        if filter.get('max_distance_high_52w'):
            conditions.append(StockMetrics.distance_to_high_52w <= filter['max_distance_high_52w'])
        
        # EMA distance
        if filter.get('min_distance_ema20'):
            conditions.append(StockMetrics.distance_to_ema20 >= filter['min_distance_ema20'])
        
        # Volume filter
        if filter.get('min_volume'):
            conditions.append(StockMetrics.avg_volume_10d >= filter['min_volume'])
        
        # ADR filter
        if filter.get('max_adr'):
            conditions.append(Stock.adr_percent <= filter['max_adr'])
        
        # EMA alignment
        if filter.get('ema20_above_ema50'):
            conditions.append(StockMetrics.ema20 > StockMetrics.ema50)
        
        if filter.get('ema50_above_ema200'):
            conditions.append(StockMetrics.ema50 > StockMetrics.ema200)
        
        # Gap filter (using distance_to_ema20 as proxy for gap)
        if filter.get('gap_pct_range'):
            min_gap, max_gap = filter['gap_pct_range']
            conditions.append(StockMetrics.distance_to_ema20 >= min_gap)
            conditions.append(StockMetrics.distance_to_ema20 <= max_gap)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by relative volume and distance to EMA20
        query = query.order_by(
            StockMetrics.relative_volume.desc(),
            StockMetrics.distance_to_ema20.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        results = []
        for stock, metrics in rows:
            # Filter out infinity and NaN values
            if (metrics.distance_to_ema20 == float('inf') or 
                metrics.distance_to_ema20 == float('-inf') or
                metrics.relative_volume == float('inf') or 
                metrics.relative_volume == float('-inf') or
                metrics.distance_to_ema20 != metrics.distance_to_ema20 or  # NaN check
                metrics.relative_volume != metrics.relative_volume):  # NaN check
                continue
            
            # Calculate gain percentage (using distance to EMA20 as proxy)
            gain_pct = metrics.distance_to_ema20 if metrics.distance_to_ema20 else 0
            
            # Ensure values are finite
            if gain_pct != gain_pct or gain_pct == float('inf') or gain_pct == float('-inf'):
                gain_pct = 0.0
            if metrics.relative_volume != metrics.relative_volume or metrics.relative_volume == float('inf') or metrics.relative_volume == float('-inf'):
                rvol = 1.0
            else:
                rvol = metrics.relative_volume
            
            results.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": map_sector_to_tradingview(stock.sector),
                "price": metrics.current_price if metrics.current_price else 0,
                "gain_pct": gain_pct,
                "rvol": rvol,
                "distance_ema20": gain_pct,
                "distance_high_52w": metrics.distance_to_high_52w if metrics.distance_to_high_52w else 0,
                "volume": metrics.avg_volume_10d if metrics.avg_volume_10d else 0,
                "market_cap": stock.market_cap if stock.market_cap else 0
            })
        
        logger.info(f"Quick scan returned {len(results)} results")
        return results
