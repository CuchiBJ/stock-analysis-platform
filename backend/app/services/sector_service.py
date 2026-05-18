from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Dict
from app.models.stock import Stock, StockMetrics, StockPrice
from app.models.sector import Sector
from app.core.cache import cache_sectors
from app.services.sector_mapping import map_sector_to_tradingview


class SectorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # @cache_sectors  # DISABLED - testing if cache is causing issues
    async def calculate_sector_performance(self) -> List[Dict]:
        """Calculate sector performance from stock metrics (simplified for performance)"""
        # Get all sectors with stocks
        result = await self.db.execute(
            select(Stock.sector, func.count(Stock.symbol).label('count'))
            .where(Stock.sector.isnot(None))
            .group_by(Stock.sector)
        )
        sectors = result.all()
        
        sector_performance = []
        
        for sector_name, count in sectors:
            # Get stocks in sector with latest metrics (simplified query)
            metrics_result = await self.db.execute(
                select(StockMetrics, Stock)
                .join(Stock, Stock.symbol == StockMetrics.symbol)
                .where(Stock.sector == sector_name)
                .where(Stock.is_active == True)
                .order_by(StockMetrics.date.desc())
                .limit(1000)  # Limit to avoid timeout
            )
            metrics = metrics_result.all()
            
            if not metrics:
                continue
            
            # Calculate average performance from metrics (simplified)
            # Use correct fields: perf_1w for weekly, perf_4w for monthly
            weekly_perfs = [m[0].perf_1w for m in metrics if m[0].perf_1w is not None]  # Weekly performance
            monthly_perfs = [m[0].perf_4w for m in metrics if m[0].perf_4w is not None]  # 4 weeks ≈ 1 month
            
            if not weekly_perfs:
                continue
            
            avg_weekly = sum(weekly_perfs) / len(weekly_perfs)
            avg_monthly = sum(monthly_perfs) / len(monthly_perfs) if monthly_perfs else avg_weekly * 4
            
            # Filter out infinity and NaN values
            import math
            if not (math.isfinite(avg_weekly) and math.isfinite(avg_monthly)):
                continue
            
            # Get SPY performance for comparison (simplified to 0)
            spy_performance = 0
            performance_vs_spy = avg_monthly - spy_performance
            
            # Determine trend
            trend = 'accelerating' if avg_weekly > 1 else 'decelerating' if avg_weekly < -1 else 'steady'
            
            # Determine strength
            strength = 'strong' if avg_monthly > 2 else 'weak' if avg_monthly < -2 else 'moderate'
            
            # Determine volume trend (simplified)
            volume_trend = 'stable'
            
            # Get sector leaders (top 3 by monthly performance)
            stock_perfs = [(m[0].symbol, m[0].perf_4w or 0) for m in metrics if m[0].perf_4w is not None]
            stock_perfs.sort(key=lambda x: x[1], reverse=True)
            leaders = [symbol for symbol, _ in stock_perfs[:3]]
            
            sector_performance.append({
                "name": sector_name,
                "performance_weekly": avg_weekly,
                "performance_monthly": avg_monthly,
                "performance_vs_spy": performance_vs_spy,
                "trend": trend,
                "strength": strength,
                "volume_trend": volume_trend,
                "stock_count": count,
                "leaders": leaders
            })
        
        return sector_performance
    
    async def _get_spy_performance(self) -> float:
        """Get SPY monthly performance for comparison"""
        try:
            result = await self.db.execute(
                select(StockPrice.date, StockPrice.close)
                .where(StockPrice.symbol == 'SPY')
                .order_by(StockPrice.date.desc())
                .limit(30)
            )
            prices = result.fetchall()
            
            if len(prices) >= 20:
                latest_price = prices[0].close
                month_ago_price = prices[19].close
                return ((latest_price - month_ago_price) / month_ago_price) * 100
            return 0
        except:
            return 0
    
    def _determine_trend(self, distances: List[float]) -> str:
        """Determine trend based on recent performance"""
        if not distances:
            return 'steady'
        
        avg = sum(distances) / len(distances)
        if avg > 1:
            return 'accelerating'
        elif avg < -1:
            return 'decelerating'
        return 'steady'
    
    def _determine_strength(self, avg_performance: float) -> str:
        """Determine strength based on performance"""
        if avg_performance > 2:
            return 'strong'
        elif avg_performance < -2:
            return 'weak'
        return 'moderate'
    
    async def _determine_volume_trend(self, symbols: List[str]) -> str:
        """Determine volume trend based on relative volume"""
        if not symbols:
            return 'stable'
        
        try:
            result = await self.db.execute(
                select(StockMetrics.relative_volume)
                .join(Stock, Stock.symbol == StockMetrics.symbol)
                .where(Stock.symbol.in_(symbols[:50]))  # Limit to 50 stocks for performance
            )
            metrics = result.scalars().all()
            
            if not metrics:
                return 'stable'
            
            avg_rvol = sum([m for m in metrics if m]) / len([m for m in metrics if m])
            
            if avg_rvol > 1.5:
                return 'increasing'
            elif avg_rvol < 0.8:
                return 'decreasing'
            return 'stable'
        except:
            return 'stable'
    
    async def _get_sector_leaders_by_performance(self, symbols: List[str], limit: int) -> List[str]:
        """Get top performing stocks in sector by monthly performance"""
        if not symbols:
            return []
        
        stock_perfs = []
        
        for symbol in symbols[:100]:  # Limit to 100 stocks for performance
            try:
                result = await self.db.execute(
                    select(StockPrice.date, StockPrice.close)
                    .where(StockPrice.symbol == symbol)
                    .order_by(StockPrice.date.desc())
                    .limit(30)
                )
                prices = result.fetchall()
                
                if len(prices) >= 20:
                    latest_price = prices[0].close
                    month_ago_price = prices[19].close
                    monthly_perf = ((latest_price - month_ago_price) / month_ago_price) * 100
                    stock_perfs.append((symbol, monthly_perf))
            except:
                continue
        
        # Sort by monthly performance descending
        stock_perfs.sort(key=lambda x: x[1], reverse=True)
        
        return [symbol for symbol, _ in stock_perfs[:limit]]

    async def get_sector_ranking(self) -> List[Sector]:
        """Get sectors ranked by performance"""
        result = await self.db.execute(
            select(Sector).order_by(Sector.rank.asc().nulls_last())
        )
        return result.scalars().all()
    
    async def get_sector_leaders(self, sector: str, limit: int = 10) -> List[Dict]:
        """Get top leaders in a specific sector"""
        result = await self.db.execute(
            select(Stock, StockMetrics)
            .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .where(Stock.sector == sector)
            .where(StockMetrics.distance_to_ema20.isnot(None))
            .order_by(StockMetrics.distance_to_ema20.desc())
            .limit(limit)
        )
        
        leaders = []
        for stock, metrics in result.all():
            leaders.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': stock.sector,
                'distance_to_ema20': metrics.distance_to_ema20,
                'relative_volume': metrics.relative_volume
            })
        
        return leaders
