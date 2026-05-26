import math
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from typing import List, Dict
from app.models.stock import Stock, StockMetrics, StockPrice
from app.models.sector import Sector
from app.core.cache import cache_sectors
from app.services.sector_mapping import map_sector_to_tradingview


class SectorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @cache_sectors
    async def calculate_sector_performance(self) -> List[Dict]:
        """Groups by market_group (~25 momentum-trading groups) — see market_group_mapping.py.
        The endpoint path /sectors/performance is preserved for compat but the unit of grouping
        changed from GICS L1 to market_group in 2026-05."""
        # Window function avoids a second GROUP BY aggregation pass
        result = await self.db.execute(text("""
            WITH latest AS (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM stock_metrics
            )
            SELECT
                s.market_group,
                l.symbol,
                l.perf_1w,
                l.perf_4w,
                l.relative_volume,
                l.pullback_quality_score,
                l.relative_strength_spy
            FROM latest l
            JOIN stocks s ON s.symbol = l.symbol
            WHERE l.rn = 1
              AND s.market_group IS NOT NULL
              AND l.avg_volume_10d  >= 500000
              AND l.current_price   >= 5.0
              AND l.adr_percent     >= 2.0
              AND l.perf_1w         IS NOT NULL
        """))
        rows = result.fetchall()

        groups: dict = defaultdict(list)
        for row in rows:
            groups[row.market_group].append(row)

        spy_perf = await self._get_spy_performance()
        sector_performance = []

        for group_name, stocks in groups.items():
            weekly_perfs  = [r.perf_1w for r in stocks if r.perf_1w  is not None]
            monthly_perfs = [r.perf_4w for r in stocks if r.perf_4w  is not None]

            if not weekly_perfs:
                continue

            avg_weekly  = sum(weekly_perfs)  / len(weekly_perfs)
            avg_monthly = sum(monthly_perfs) / len(monthly_perfs) if monthly_perfs else avg_weekly * 4

            if not (math.isfinite(avg_weekly) and math.isfinite(avg_monthly)):
                continue

            leaders_sorted = sorted(
                [r for r in stocks if r.pullback_quality_score is not None],
                key=lambda r: (r.pullback_quality_score or 0) * 0.6 + (r.relative_strength_spy or 100) * 0.4,
                reverse=True
            )
            leaders = [r.symbol for r in leaders_sorted[:3]]
            avg_rvol = sum(r.relative_volume for r in stocks if r.relative_volume) / max(len(stocks), 1)

            sector_performance.append({
                "name":                group_name,
                "performance_weekly":  round(avg_weekly,  2),
                "performance_monthly": round(avg_monthly, 2),
                "performance_vs_spy":  round(avg_monthly - spy_perf, 2),
                "trend":     "accelerating" if avg_weekly > 1 else "decelerating" if avg_weekly < -1 else "steady",
                "strength":  "strong" if avg_monthly > 2 else "weak" if avg_monthly < -2 else "moderate",
                "volume_trend": "increasing" if avg_rvol > 1.5 else "decreasing" if avg_rvol < 0.8 else "stable",
                "stock_count": len(stocks),
                "leaders":   leaders,
            })

        sector_performance.sort(key=lambda x: x["performance_monthly"], reverse=True)
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
