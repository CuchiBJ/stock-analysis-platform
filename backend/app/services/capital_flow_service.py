"""Capital Flow Service - Calculate real sector capital flows"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Dict
from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.sector_mapping import map_sector_to_tradingview
import logging

logger = logging.getLogger(__name__)


class CapitalFlowService:
    """Service for calculating sector capital flows"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_capital_flows(self) -> List[Dict]:
        """Calculate capital flows by sector"""
        # Get all sectors with stocks
        result = await self.db.execute(
            select(Stock.sector, func.count(Stock.symbol).label('count'))
            .where(Stock.sector.isnot(None))
            .group_by(Stock.sector)
        )
        sectors = result.all()
        
        capital_flows = []
        
        for sector_name, count in sectors:
            # Get stocks in sector with metrics
            stocks_result = await self.db.execute(
                select(Stock, StockMetrics)
                .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
                .where(Stock.sector == sector_name)
            )
            stocks_with_metrics = stocks_result.all()
            
            if not stocks_with_metrics:
                continue
            
            # Calculate sector metrics
            total_volume = 0
            total_rvol = 0
            total_change = 0
            stock_count = 0
            
            for stock, metrics in stocks_with_metrics:
                if metrics.avg_volume_10d and metrics.relative_volume and metrics.distance_to_ema20:
                    # Filter out infinity and NaN values
                    if (metrics.relative_volume == float('inf') or 
                        metrics.relative_volume == float('-inf') or 
                        metrics.distance_to_ema20 == float('inf') or 
                        metrics.distance_to_ema20 == float('-inf') or
                        metrics.relative_volume != metrics.relative_volume or  # NaN check
                        metrics.distance_to_ema20 != metrics.distance_to_ema20):  # NaN check
                        continue
                    
                    total_volume += metrics.avg_volume_10d
                    total_rvol += metrics.relative_volume
                    total_change += metrics.distance_to_ema20
                    stock_count += 1
            
            if stock_count == 0:
                continue
            
            avg_rvol = total_rvol / stock_count
            avg_change = total_change / stock_count
            
            # Ensure values are finite
            if avg_rvol != avg_rvol or avg_rvol == float('inf') or avg_rvol == float('-inf'):
                avg_rvol = 1.0
            if avg_change != avg_change or avg_change == float('inf') or avg_change == float('-inf'):
                avg_change = 0.0
            
            # Determine flow direction based on RVOL and price change
            if avg_change > 0:
                flow = 'inflow'  # Positive performance = inflow (green)
            elif avg_change < 0:
                flow = 'outflow'  # Negative performance = outflow (red)
            else:
                flow = 'neutral'
            
            # Determine strength
            if avg_rvol > 2.0:
                strength = 'strong'
            elif avg_rvol > 1.5:
                strength = 'moderate'
            else:
                strength = 'weak'
            
            # Determine acceleration
            if avg_rvol > 1.5 and avg_change > 1:
                acceleration = 'accelerating'
            elif avg_rvol > 1.5 and avg_change < -1:
                acceleration = 'decelerating'
            else:
                acceleration = 'stable'
            
            # Get sector leaders (top 3 by RVOL)
            leaders = self._get_sector_leaders(stocks_with_metrics, 3)
            
            capital_flows.append({
                'sector': map_sector_to_tradingview(sector_name),
                'flow': flow,
                'strength': strength,
                'change_pct': avg_change,
                'rvol': avg_rvol,
                'acceleration': acceleration,
                'leaders': leaders,
                'stock_count': stock_count
            })
        
        # Sort by performance (change_pct) descending, then by RVOL
        capital_flows.sort(key=lambda x: (x['change_pct'], x['rvol']), reverse=True)
        
        return capital_flows[:10]  # Return top 10 sectors
    
    def _get_sector_leaders(self, stocks_with_metrics: List[tuple], limit: int) -> List[str]:
        """Get top stocks in sector by RVOL"""
        if not stocks_with_metrics:
            return []
        
        # Sort by RVOL
        sorted_stocks = sorted(
            [(stock, metrics) for stock, metrics in stocks_with_metrics if metrics.relative_volume],
            key=lambda x: x[1].relative_volume,
            reverse=True
        )
        
        return [stock.symbol for stock, metrics in sorted_stocks[:limit]]
