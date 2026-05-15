from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Dict, Optional
from app.models.stock import Stock, StockMetrics, StockPrice
from app.data.processors.relative_strength import calculate_rs_rank, calculate_rs_momentum, detect_early_leader
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class RelativeStrengthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_rs_for_symbol(
        self,
        symbol: str,
        benchmark_symbol: str = "SPY"
    ) -> Optional[float]:
        """Calculate relative strength for a symbol vs benchmark"""
        try:
            # Get symbol prices
            symbol_result = await self.db.execute(
                select(StockPrice)
                .where(StockPrice.symbol == symbol.upper())
                .order_by(StockPrice.date.desc())
                .limit(60)
            )
            symbol_prices = symbol_result.scalars().all()
            
            # Get benchmark prices
            benchmark_result = await self.db.execute(
                select(StockPrice)
                .where(StockPrice.symbol == benchmark_symbol)
                .order_by(StockPrice.date.desc())
                .limit(60)
            )
            benchmark_prices = benchmark_result.scalars().all()
            
            if len(symbol_prices) < 20 or len(benchmark_prices) < 20:
                logger.warning(f"Not enough data for RS calculation: {symbol}")
                return None
            
            # Convert to DataFrames
            symbol_df = pd.DataFrame([{
                'date': p.date,
                'close': p.close
            } for p in reversed(symbol_prices)])
            
            benchmark_df = pd.DataFrame([{
                'date': p.date,
                'close': p.close
            } for p in reversed(benchmark_prices)])
            
            # Calculate RS ratio
            symbol_close = symbol_df['close'].iloc[-1]
            benchmark_close = benchmark_df['close'].iloc[-1]
            
            if benchmark_close == 0:
                return None
            
            rs = (symbol_close / benchmark_close) * 100
            return float(rs)
            
        except Exception as e:
            logger.error(f"Error calculating RS for {symbol}: {e}")
            return None

    async def update_rs_metrics(self, symbols: List[str]) -> int:
        """Update RS metrics for a list of symbols"""
        count = 0
        
        for symbol in symbols:
            try:
                # Calculate RS vs SPY
                rs_spy = await self.calculate_rs_for_symbol(symbol, "SPY")
                
                # Calculate RS vs QQQ
                rs_qqq = await self.calculate_rs_for_symbol(symbol, "QQQ")
                
                # Get latest metrics
                result = await self.db.execute(
                    select(StockMetrics)
                    .where(StockMetrics.symbol == symbol.upper())
                    .order_by(StockMetrics.date.desc())
                    .limit(1)
                )
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    metrics.relative_strength_spy = rs_spy
                    metrics.relative_strength_qqq = rs_qqq
                    self.db.add(metrics)
                    count += 1
                    
            except Exception as e:
                logger.error(f"Failed to update RS for {symbol}: {e}")
                continue
        
        await self.db.commit()
        logger.info(f"Updated RS metrics for {count} symbols")
        return count

    async def get_rs_ranking(
        self,
        benchmark: str = "SPY",
        limit: int = 100
    ) -> List[Dict]:
        """Get stocks ranked by relative strength"""
        # Get all stocks with RS metrics (latest date only)
        rs_column = StockMetrics.relative_strength_spy if benchmark == "SPY" else StockMetrics.relative_strength_qqq
        
        # Use subquery to get only the latest metrics per symbol
        from sqlalchemy import func
        subquery = select(
            StockMetrics.symbol,
            func.max(StockMetrics.date).label('max_date')
        ).group_by(StockMetrics.symbol).subquery()
        
        result = await self.db.execute(
            select(Stock, StockMetrics).join(
                StockMetrics, Stock.symbol == StockMetrics.symbol
            ).join(
                subquery,
                (StockMetrics.symbol == subquery.c.symbol) &
                (StockMetrics.date == subquery.c.max_date)
            ).where(rs_column.isnot(None))
        )
        rows = result.all()
        
        if not rows:
            return []
        
        # Extract RS values for ranking
        rs_values = [getattr(m, f"relative_strength_{benchmark.lower()}") for _, m in rows]
        
        # Calculate rankings
        ranked_stocks = []
        for stock, metrics in rows:
            rs_value = getattr(metrics, f"relative_strength_{benchmark.lower()}")
            rank = calculate_rs_rank(rs_value, rs_values)
            ranked_stocks.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                f"rs_{benchmark.lower()}": rs_value,
                "rs_rank": rank,
                "price": metrics.ema20
            })
        
        # Sort by rank descending
        ranked_stocks.sort(key=lambda x: x["rs_rank"], reverse=True)
        
        return ranked_stocks[:limit]

    async def get_leaders_vs_benchmark(
        self,
        benchmark: str = "SPY",
        limit: int = 50
    ) -> List[Dict]:
        """Get stocks outperforming benchmark"""
        rs_column = StockMetrics.relative_strength_spy if benchmark == "SPY" else StockMetrics.relative_strength_qqq
        
        result = await self.db.execute(
            select(Stock, StockMetrics).join(
                StockMetrics, Stock.symbol == StockMetrics.symbol
            ).where(rs_column > 100)
            .order_by(rs_column.desc())
            .limit(limit)
        )
        rows = result.all()
        
        leaders = []
        for stock, metrics in rows:
            leaders.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                "rs_spy": metrics.relative_strength_spy,
                "rs_qqq": metrics.relative_strength_qqq,
                "price": metrics.ema20,
                "rs_rank": getattr(metrics, f"relative_strength_{benchmark.lower()}", 0)
            })
        
        return leaders

    async def get_rs_momentum_leaders(
        self,
        benchmark: str = "SPY",
        limit: int = 50
    ) -> List[Dict]:
        """Get stocks with improving relative strength"""
        # This would require historical RS data
        # For MVP, use current RS + momentum from price
        result = await self.db.execute(
            select(Stock, StockMetrics).join(
                StockMetrics, Stock.symbol == StockMetrics.symbol
            ).where(
                and_(
                    StockMetrics.ema20 > StockMetrics.ema50,
                    StockMetrics.relative_strength_spy > 100,
                    StockMetrics.distance_to_ema20 > 0
                )
            ).order_by(StockMetrics.relative_strength_spy.desc())
            .limit(limit)
        )
        rows = result.all()
        
        leaders = []
        for stock, metrics in rows:
            leaders.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                "rs_spy": metrics.relative_strength_spy,
                "rs_qqq": metrics.relative_strength_qqq,
                "price": metrics.ema20,
                "momentum_score": metrics.distance_to_ema20
            })
        
        return leaders

    async def get_sector_rs_leaders(
        self,
        sector: str,
        benchmark: str = "SPY",
        limit: int = 20
    ) -> List[Dict]:
        """Get top RS leaders within a specific sector"""
        rs_column = StockMetrics.relative_strength_spy if benchmark == "SPY" else StockMetrics.relative_strength_qqq
        
        result = await self.db.execute(
            select(Stock, StockMetrics).join(
                StockMetrics, Stock.symbol == StockMetrics.symbol
            ).where(
                and_(
                    Stock.sector == sector,
                    rs_column.isnot(None)
                )
            ).order_by(rs_column.desc())
            .limit(limit)
        )
        rows = result.all()
        
        leaders = []
        for stock, metrics in rows:
            leaders.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                f"rs_{benchmark.lower()}": getattr(metrics, f"relative_strength_{benchmark.lower()}"),
                "price": metrics.ema20
            })
        
        return leaders
