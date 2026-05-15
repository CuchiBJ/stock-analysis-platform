from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.scoring_service import ScoringService
from app.services.sector_mapping import map_sector_to_tradingview
from app.core.cache import cache_indices
from typing import List, Dict
from datetime import datetime


class LeaderService:
    """Service for fetching and preparing leader stock data"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scoring_service = ScoringService(db)
    
    @cache_indices
    async def get_leaders(self, limit: int = 50, sort: str = 'score') -> List[Dict]:
        """Get top leader stocks with full data"""
        # Get scored stocks
        scored_stocks = await self.scoring_service.calculate_scores(limit * 2)  # Get more to filter
        
        leaders = []
        for item in scored_stocks:
            stock = item['stock'] if 'stock' in item else None
            metrics = item['metrics']
            score = item['score']
            
            if not stock or not metrics:
                continue
            
            # Get latest price
            price_result = await self.db.execute(
                select(StockPrice)
                .where(StockPrice.symbol == stock.symbol)
                .order_by(StockPrice.date.desc())
                .limit(1)
            )
            price_data = price_result.scalar_one_or_none()
            
            # Calculate gain percentage
            gain_pct = 0
            if price_data:
                gain_pct = ((price_data.close - price_data.open) / price_data.open) * 100
            
            # Detect badges
            badges = self._detect_badges(metrics, price_data)
            
            # Calculate trend quality
            trend_quality = self._calculate_trend_quality(metrics)
            
            # Calculate RS rank (simplified)
            rs_rank = self._calculate_rs_rank(metrics, scored_stocks)
            
            leaders.append({
                'symbol': stock.symbol,
                'name': stock.name,
                'sector': map_sector_to_tradingview(stock.sector),
                'price': price_data.close if price_data else 0,
                'gain_pct': gain_pct,
                'rvol': metrics.relative_volume,
                'rs_rank': rs_rank,
                'volume': metrics.avg_volume_10d if metrics.avg_volume_10d else 0,
                'market_cap': stock.market_cap if stock.market_cap else 0,
                'distance_ath': metrics.distance_to_high_52w if metrics.distance_to_high_52w else 0,
                'float': stock.float_shares if stock.float_shares else 0,
                'trend_quality': trend_quality,
                'score': score,
                'badges': badges,
                'mini_chart': self._generate_mini_chart_data(metrics)  # Placeholder
            })
        
        # Sort based on requested criteria
        if sort == 'gain':
            leaders.sort(key=lambda x: x['gain_pct'], reverse=True)
        elif sort == 'rvol':
            leaders.sort(key=lambda x: x['rvol'] or 0, reverse=True)
        else:  # score
            leaders.sort(key=lambda x: x['score'], reverse=True)
        
        return leaders[:limit]
    
    def _detect_badges(self, metrics: StockMetrics, price_data: StockPrice | None) -> List[str]:
        """Detect and return badges for a stock"""
        badges = []
        
        if not metrics:
            return badges
        
        # Breakout detection
        if metrics.distance_to_ema20 and metrics.distance_to_ema20 > 2:
            badges.append('breakout')
        
        # Near ATH
        if metrics.distance_to_high_52w and metrics.distance_to_high_52w >= -2:
            badges.append('near_ath')
        
        # Unusual volume
        if metrics.relative_volume and metrics.relative_volume > 2:
            badges.append('unusual_volume')
        
        # EMA20 reclaim
        if metrics.distance_to_ema20 and metrics.distance_to_ema20 > 0:
            badges.append('ema20_reclaim')
        
        # Strong RS
        if metrics.distance_to_ema20 and metrics.distance_to_ema20 > 3:
            badges.append('strong_rs')
        
        return badges
    
    def _calculate_trend_quality(self, metrics: StockMetrics) -> int:
        """Calculate trend quality score (0-10)"""
        if not metrics.ema20 or not metrics.ema50 or not metrics.ema200:
            return 5
        
        score = 5
        
        # EMA alignment
        if metrics.ema20 > metrics.ema50:
            score += 2
        if metrics.ema50 > metrics.ema200:
            score += 2
        if metrics.ema20 > metrics.ema200:
            score += 1
        
        return min(10, max(0, score))
    
    def _calculate_rs_rank(self, metrics: StockMetrics, all_scores: List[Dict]) -> int:
        """Calculate relative strength rank (1-100)"""
        if not metrics.distance_to_ema20:
            return 50
        
        # Simple percentile rank based on distance to EMA20
        distances = [item['metrics'].distance_to_ema20 for item in all_scores if item['metrics'].distance_to_ema20]
        distances.sort(reverse=True)
        
        try:
            rank = distances.index(metrics.distance_to_ema20) + 1
            percentile = (rank / len(distances)) * 100
            return 100 - percentile  # Higher is better
        except:
            return 50
    
    def _generate_mini_chart_data(self, metrics: StockMetrics) -> List[float]:
        """Generate mini chart data (placeholder)"""
        # In production, this would fetch actual price history
        # For now, return synthetic data based on distance to EMA20
        if not metrics.distance_to_ema20:
            return [0, 0, 0, 0, 0]
        
        base = 100
        trend = metrics.distance_to_ema20 / 5
        
        data = []
        for i in range(20):
            noise = (hash(str(i)) % 10 - 5) / 10
            value = base + (trend * i) + noise
            data.append(value)
        
        return data
