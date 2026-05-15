from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.repositories.stock_repository import StockRepository
from app.data.sources.polygon_client import PolygonClient
from app.data.processors.momentum import (
    calculate_ema, calculate_rsi,
    calculate_relative_strength,
    calculate_distance_to_ema,
    calculate_relative_volume
)
from app.models.stock import Stock, StockPrice, StockMetrics
import pandas as pd


class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StockRepository(db)
        self.polygon = PolygonClient()

    async def get_stock_with_metrics(self, symbol: str) -> Optional[dict]:
        """Get stock with latest metrics"""
        stock = await self.repo.get_by_symbol(symbol)
        if not stock:
            return None
        
        prices = await self.repo.get_prices(symbol, days=60)
        metrics = await self.repo.get_latest_metrics(symbol)
        
        return {
            "stock": stock,
            "prices": prices,
            "metrics": metrics
        }

    async def calculate_metrics_for_symbol(self, symbol: str) -> StockMetrics:
        """Calculate and store metrics for a symbol"""
        prices = await self.repo.get_prices(symbol, days=200)
        if not prices:
            raise ValueError(f"No price data for {symbol}")
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'date': p.date,
            'close': p.close,
            'volume': p.volume
        } for p in prices])
        df = df.sort_values('date')
        
        close_prices = df['close']
        volumes = df['volume']
        
        # Calculate indicators
        ema20 = calculate_ema(close_prices, 20).iloc[-1]
        ema50 = calculate_ema(close_prices, 50).iloc[-1]
        ema200 = calculate_ema(close_prices, 200).iloc[-1]
        rsi = calculate_rsi(close_prices, 14).iloc[-1]
        
        current_price = close_prices.iloc[-1]
        dist_ema20 = calculate_distance_to_ema(current_price, ema20)
        dist_ema50 = calculate_distance_to_ema(current_price, ema50)
        
        avg_vol_20d = volumes.tail(20).mean()
        rel_vol = calculate_relative_volume(volumes.iloc[-1], avg_vol_20d)
        
        # Get SPY data for relative strength (simplified)
        # In production, fetch SPY data separately
        rs_spy = 100.0  # Placeholder
        
        metrics = StockMetrics(
            symbol=symbol.upper(),
            date=df['date'].iloc[-1],
            ema20=float(ema20),
            ema50=float(ema50),
            ema200=float(ema200),
            rsi=float(rsi),
            relative_strength_spy=rs_spy,
            distance_to_ema20=dist_ema20,
            distance_to_ema50=dist_ema50,
            avg_volume_20d=int(avg_vol_20d),
            relative_volume=rel_vol
        )
        
        self.db.add(metrics)
        await self.db.commit()
        await self.db.refresh(metrics)
        
        return metrics
