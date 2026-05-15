from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.stock import Stock, StockPrice, StockMetrics
from app.models.index import Index
from app.core.cache import cache_indices
from typing import List
from datetime import datetime


class IndexService:
    def __init__(self):
        # Major ETF symbols
        self.index_symbols = ['SPY', 'QQQ', 'IWM', 'DIA']
    
    @cache_indices
    async def get_all_indices(self, db: AsyncSession) -> List[dict]:
        """Get all major indices with current data"""
        indices_data = []
        
        for symbol in self.index_symbols:
            index_data = await self._get_index_data(db, symbol)
            if index_data:
                indices_data.append(index_data)
        
        return indices_data
    
    async def _get_index_data(self, db: AsyncSession, symbol: str) -> dict | None:
        """Get data for a single index"""
        # Get stock data (treated as index ETF)
        result = await db.execute(
            select(Stock).where(Stock.symbol == symbol)
        )
        stock = result.scalar_one_or_none()
        
        if not stock:
            return None
        
        # Get latest metrics
        metrics_result = await db.execute(
            select(StockMetrics)
            .where(StockMetrics.symbol == symbol)
            .order_by(StockMetrics.date.desc())
            .limit(1)
        )
        metrics = metrics_result.scalar_one_or_none()
        
        if not metrics:
            return None
        
        # Get latest price
        price_result = await db.execute(
            select(StockPrice)
            .where(StockPrice.symbol == symbol)
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        price_data = price_result.scalar_one_or_none()
        
        # Calculate daily change
        daily_change_pct = 0
        if price_data and price_data.close:
            daily_change_pct = ((price_data.close - price_data.open) / price_data.open) * 100
        
        # Determine trend and strength
        trend_short = self._determine_trend(metrics)
        strength = self._determine_strength(metrics, daily_change_pct)
        
        return {
            'symbol': symbol,
            'name': stock.name,
            'current_price': price_data.close if price_data else 0,
            'daily_change_pct': daily_change_pct,
            'gap_pct': self._calculate_gap_pct(metrics),
            'relative_volume': metrics.relative_volume,
            'distance_ema20': metrics.distance_to_ema20,
            'trend_short': trend_short,
            'strength': strength,
            'updated_at': datetime.utcnow().isoformat()
        }
    
    def _determine_trend(self, metrics: StockMetrics) -> str:
        """Determine short-term trend based on EMAs"""
        if not metrics.ema20 or not metrics.ema50:
            return 'neutral'
        
        if metrics.ema20 > metrics.ema50:
            return 'bullish'
        elif metrics.ema20 < metrics.ema50:
            return 'bearish'
        return 'neutral'
    
    def _determine_strength(self, metrics: StockMetrics, daily_change_pct: float) -> str:
        """Determine strength based on multiple factors"""
        if daily_change_pct > 1:
            return 'bullish'
        elif daily_change_pct < -1:
            return 'bearish'
        return 'neutral'
    
    def _calculate_gap_pct(self, metrics: StockMetrics) -> float | None:
        """Calculate gap percentage (placeholder - needs price history)"""
        # TODO: Implement proper gap calculation using previous day's close
        return None
