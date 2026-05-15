from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.stock import Stock, StockPrice, StockMetrics
from app.services.sector_mapping import map_sector_to_tradingview
from app.core.cache import cache_breadth
from typing import List, Dict
from datetime import datetime


class BreadthService:
    @cache_breadth
    async def calculate_breadth(self, db: AsyncSession) -> Dict:
        """Calculate market breadth metrics"""
        # Get all stocks with latest metrics
        result = await db.execute(
            select(StockMetrics)
            .where(StockMetrics.date == select(func.max(StockMetrics.date)).scalar_subquery())
        )
        all_metrics = result.scalars().all()
        
        if not all_metrics:
            return self._empty_breadth()
        
        # Calculate advance/decline
        advancers = sum(1 for m in all_metrics if m.distance_to_ema20 and m.distance_to_ema20 > 0)
        decliners = sum(1 for m in all_metrics if m.distance_to_ema20 and m.distance_to_ema20 < 0)
        ad_ratio = advancers / decliners if decliners > 0 else advancers
        
        # Calculate new highs/lows (using 52w distance)
        new_highs = sum(1 for m in all_metrics if m.distance_to_high_52w and m.distance_to_high_52w >= -2)
        new_lows = sum(1 for m in all_metrics if m.distance_to_high_52w and m.distance_to_high_52w <= -98)
        
        # Calculate above EMA
        above_ema20 = sum(1 for m in all_metrics if m.distance_to_ema20 and m.distance_to_ema20 > 0)
        above_ema50 = sum(1 for m in all_metrics if m.distance_to_ema50 and m.distance_to_ema50 > 0)
        total = len(all_metrics)
        
        above_ema20_pct = (above_ema20 / total * 100) if total > 0 else 0
        above_ema50_pct = (above_ema50 / total * 100) if total > 0 else 0
        
        # Color breakdown
        green_stocks = advancers
        red_stocks = decliners
        neutral_stocks = total - advancers - decliners
        
        # Sector breadth
        sector_breadth = await self._calculate_sector_breadth(db, all_metrics)
        
        return {
            'advance_decline': {
                'advancers': advancers,
                'decliners': decliners,
                'ratio': round(ad_ratio, 2)
            },
            'new_highs_lows': {
                'new_highs': new_highs,
                'new_lows': new_lows
            },
            'above_ema': {
                'above_ema20': round(above_ema20_pct, 1),
                'above_ema50': round(above_ema50_pct, 1)
            },
            'color_breakdown': {
                'green_stocks': green_stocks,
                'red_stocks': red_stocks,
                'neutral_stocks': neutral_stocks
            },
            'sector_breadth': sector_breadth
        }
    
    async def _calculate_sector_breadth(self, db: AsyncSession, all_metrics: List[StockMetrics]) -> List[Dict]:
        """Calculate breadth by sector"""
        sector_breadth = []
        
        # Get stocks with sector info
        result = await db.execute(
            select(Stock, StockMetrics)
            .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .where(Stock.sector.isnot(None))
        )
        stocks_with_metrics = result.all()
        
        # Group by sector
        sector_data: Dict[str, List[StockMetrics]] = {}
        for stock, metrics in stocks_with_metrics:
            if stock.sector not in sector_data:
                sector_data[stock.sector] = []
            sector_data[stock.sector].append(metrics)
        
        # Calculate for each sector
        for sector, metrics_list in sector_data.items():
            advancers = sum(1 for m in metrics_list if m.distance_to_ema20 and m.distance_to_ema20 > 0)
            decliners = sum(1 for m in metrics_list if m.distance_to_ema20 and m.distance_to_ema20 < 0)
            
            # Determine strength
            ratio = advancers / decliners if decliners > 0 else advancers
            if ratio >= 2:
                strength = 'strong'
            elif ratio >= 1:
                strength = 'moderate'
            else:
                strength = 'weak'
            
            sector_breadth.append({
                'sector': map_sector_to_tradingview(sector),
                'advancers': advancers,
                'decliners': decliners,
                'strength': strength
            })
        
        # Sort by advancers descending
        sector_breadth.sort(key=lambda x: x['advancers'], reverse=True)
        
        return sector_breadth[:10]  # Return top 10 sectors
    
    def _empty_breadth(self) -> Dict:
        """Return empty breadth structure"""
        return {
            'advance_decline': {
                'advancers': 0,
                'decliners': 0,
                'ratio': 0.0
            },
            'new_highs_lows': {
                'new_highs': 0,
                'new_lows': 0
            },
            'above_ema': {
                'above_ema20': 0.0,
                'above_ema50': 0.0
            },
            'color_breakdown': {
                'green_stocks': 0,
                'red_stocks': 0,
                'neutral_stocks': 0
            },
            'sector_breadth': []
        }
