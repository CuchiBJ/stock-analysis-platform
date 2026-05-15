from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.stock import Stock, StockMetrics
from typing import List, Dict
from app.core.cache import cache_indices


class ScoringService:
    """Service for calculating stock scores based on multiple factors"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_scores(self, limit: int = 100) -> List[Dict]:
        """Calculate scores for all stocks and return top ranked"""
        # Get all stocks with metrics
        result = await self.db.execute(
            select(Stock, StockMetrics)
            .join(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .where(Stock.is_active == True)
        )
        stocks_with_metrics = result.all()
        
        scored_stocks = []
        
        for stock, metrics in stocks_with_metrics:
            score = self._calculate_total_score(metrics)
            scored_stocks.append({
                'stock': stock,
                'metrics': metrics,
                'score': score
            })
        
        # Sort by score descending
        scored_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_stocks[:limit]
    
    def _calculate_total_score(self, metrics: StockMetrics) -> float:
        """Calculate total score from individual components"""
        breakdown = self._calculate_score_breakdown(metrics)
        return (
            breakdown['rs'] * 0.25 +
            breakdown['rvol'] * 0.20 +
            breakdown['momentum'] * 0.20 +
            breakdown['sector'] * 0.15 +
            breakdown['trend'] * 0.10 +
            breakdown['proximity'] * 0.05 +
            breakdown['breakout'] * 0.05
        )
    
    def _calculate_score_breakdown(self, metrics: StockMetrics) -> Dict[str, float]:
        """Calculate individual score components (0-100 scale)"""
        breakdown = {
            'rs': self._score_rs(metrics),
            'rvol': self._score_rvol(metrics),
            'momentum': self._score_momentum(metrics),
            'sector': self._score_sector(metrics),
            'trend': self._score_trend(metrics),
            'proximity': self._score_proximity(metrics),
            'breakout': self._score_breakout(metrics),
        }
        return breakdown
    
    def _score_rs(self, metrics: StockMetrics) -> float:
        """Score based on relative strength (0-100)"""
        # Using distance to EMA20 as proxy for RS
        if metrics.distance_to_ema20 is None:
            return 50
        
        # Normalize: -5% to +5% -> 0 to 100
        normalized = (metrics.distance_to_ema20 + 5) / 10
        return max(0, min(100, normalized * 100))
    
    def _score_rvol(self, metrics: StockMetrics) -> float:
        """Score based on relative volume (0-100)"""
        if metrics.relative_volume is None:
            return 50
        
        # RVOL > 1.5 is good, < 0.5 is bad
        if metrics.relative_volume >= 1.5:
            return 100
        elif metrics.relative_volume >= 1.0:
            return 75
        elif metrics.relative_volume >= 0.8:
            return 50
        elif metrics.relative_volume >= 0.5:
            return 25
        else:
            return 10
    
    def _score_momentum(self, metrics: StockMetrics) -> float:
        """Score based on momentum indicators (0-100)"""
        if metrics.ema20 is None or metrics.ema50 is None or metrics.ema200 is None:
            return 50
        
        # Check EMA alignment
        ema_score = 0
        if metrics.ema20 > metrics.ema50:
            ema_score += 30
        if metrics.ema50 > metrics.ema200:
            ema_score += 30
        if metrics.ema20 > metrics.ema200:
            ema_score += 40
        
        return ema_score
    
    def _score_sector(self, metrics: StockMetrics) -> float:
        """Score based on sector strength (0-100)"""
        # Placeholder - would use sector performance data
        return 50
    
    def _score_trend(self, metrics: StockMetrics) -> float:
        """Score based on trend quality (0-100)"""
        if metrics.ema20 is None or metrics.ema50 is None:
            return 50
        
        # Trend quality based on EMA alignment and slope
        if metrics.ema20 > metrics.ema50:
            return 75
        return 25
    
    def _score_proximity(self, metrics: StockMetrics) -> float:
        """Score based on proximity to 52-week high (0-100)"""
        if metrics.distance_to_high_52w is None:
            return 50
        
        # Closer to ATH is better
        if metrics.distance_to_high_52w >= -2:
            return 100
        elif metrics.distance_to_high_52w >= -5:
            return 75
        elif metrics.distance_to_high_52w >= -10:
            return 50
        elif metrics.distance_to_high_52w >= -20:
            return 25
        else:
            return 10
    
    def _score_breakout(self, metrics: StockMetrics) -> float:
        """Score based on breakout potential (0-100)"""
        # Placeholder - would check for consolidation patterns
        return 50
