"""
Universe Enrichment Layer

Enrich each ticker with:
- Sector (GICS classification)
- Industry (GICS sub-industry)
- Float (shares outstanding)
- Liquidity (average volume, average dollar volume)
- ATR (Average True Range)
- Volatility profile
- Institutional quality
- RS baseline (relative strength vs SPY/QQQ)
- Tradability metrics
- Market cap tier
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, replace
from enum import Enum
import statistics

from app.universe.sources.universe_source import TickerInfo
from app.universe.normalization.normalizer import MarketCapNormalizer

logger = logging.getLogger(__name__)


class VolatilityProfile(Enum):
    """Volatility profile classification"""
    LOW = "low"  # ATR < 2%
    MODERATE = "moderate"  # ATR 2-5%
    HIGH = "high"  # ATR 5-10%
    EXTREME = "extreme"  # ATR > 10%


@dataclass
class EnrichedTicker:
    """Enriched ticker information"""
    symbol: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    float_shares: Optional[int] = None
    avg_volume_20d: Optional[int] = None
    avg_dollar_volume_20d: Optional[float] = None
    atr: Optional[float] = None
    atr_percent: Optional[float] = None
    volatility_profile: Optional[VolatilityProfile] = None
    institutional_quality_score: Optional[float] = None  # 0-100
    rs_baseline_spy: Optional[float] = None
    rs_baseline_qqq: Optional[float] = None
    tradability_score: Optional[float] = None  # 0-100
    market_cap_tier: Optional[str] = None
    last_enriched_at: datetime = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "sector": self.sector,
            "industry": self.industry,
            "float_shares": self.float_shares,
            "avg_volume_20d": self.avg_volume_20d,
            "avg_dollar_volume_20d": self.avg_dollar_volume_20d,
            "atr": self.atr,
            "atr_percent": self.atr_percent,
            "volatility_profile": self.volatility_profile.value if self.volatility_profile else None,
            "institutional_quality_score": self.institutional_quality_score,
            "rs_baseline_spy": self.rs_baseline_spy,
            "rs_baseline_qqq": self.rs_baseline_qqq,
            "tradability_score": self.tradability_score,
            "market_cap_tier": self.market_cap_tier,
            "last_enriched_at": self.last_enriched_at.isoformat() if self.last_enriched_at else None
        }


class UniverseEnricher:
    """
    Universe Enricher
    
    Enrich each ticker with:
    - Sector/industry (GICS classification)
    - Float (shares outstanding)
    - Liquidity metrics
    - ATR and volatility profile
    - Institutional quality score
    - RS baseline (vs SPY/QQQ)
    - Tradability score
    - Market cap tier
    """
    
    def __init__(self):
        self.market_cap_normalizer = MarketCapNormalizer()
    
    def enrich_ticker(
        self,
        ticker_info: TickerInfo,
        price_data: Optional[Dict[str, Any]] = None
    ) -> EnrichedTicker:
        """
        Enrich a single ticker.
        
        Args:
            ticker_info: Ticker information
            price_data: Optional price data for enrichment
            
        Returns:
            EnrichedTicker
        """
        enriched = EnrichedTicker(
            symbol=ticker_info.symbol,
            sector=ticker_info.sector,
            industry=ticker_info.industry,
            last_enriched_at=datetime.utcnow()
        )
        
        if price_data:
            # Calculate liquidity metrics
            enriched.avg_volume_20d = price_data.get("avg_volume_20d")
            current_price = price_data.get("close")
            if enriched.avg_volume_20d and current_price:
                enriched.avg_dollar_volume_20d = enriched.avg_volume_20d * current_price
            
            # Calculate ATR
            enriched.atr = price_data.get("atr")
            if enriched.atr and current_price:
                enriched.atr_percent = (enriched.atr / current_price) * 100
                enriched.volatility_profile = self._classify_volatility(enriched.atr_percent)
            
            # Float
            enriched.float_shares = price_data.get("float_shares")
            
            # Market cap tier
            market_cap = price_data.get("market_cap") or ticker_info.market_cap
            if market_cap:
                enriched.market_cap_tier = self.market_cap_normalizer.get_tier(market_cap)
            
            # RS baseline
            enriched.rs_baseline_spy = price_data.get("rs_spy")
            enriched.rs_baseline_qqq = price_data.get("rs_qqq")
            
            # Institutional quality score
            enriched.institutional_quality_score = self._calculate_institutional_quality(
                enriched.avg_dollar_volume_20d,
                enriched.float_shares,
                enriched.volatility_profile,
                market_cap
            )
            
            # Tradability score
            enriched.tradability_score = self._calculate_tradability(
                enriched.avg_dollar_volume_20d,
                enriched.atr_percent,
                current_price
            )
        
        return enriched
    
    def enrich_batch(
        self,
        tickers: List[TickerInfo],
        price_data_map: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[EnrichedTicker]:
        """
        Enrich multiple tickers.
        
        Args:
            tickers: List of ticker information
            price_data_map: Optional mapping of symbol to price data
            
        Returns:
            List of EnrichedTicker
        """
        enriched_tickers = []
        
        for ticker in tickers:
            price_data = price_data_map.get(ticker.symbol) if price_data_map else None
            enriched = self.enrich_ticker(ticker, price_data)
            enriched_tickers.append(enriched)
        
        logger.info(f"Enriched {len(enriched_tickers)} tickers")
        return enriched_tickers
    
    def _classify_volatility(self, atr_percent: float) -> VolatilityProfile:
        """Classify volatility profile"""
        if atr_percent < 2:
            return VolatilityProfile.LOW
        elif atr_percent < 5:
            return VolatilityProfile.MODERATE
        elif atr_percent < 10:
            return VolatilityProfile.HIGH
        else:
            return VolatilityProfile.EXTREME
    
    def _calculate_institutional_quality(
        self,
        avg_dollar_volume: Optional[float],
        float_shares: Optional[int],
        volatility_profile: Optional[VolatilityProfile],
        market_cap: Optional[float]
    ) -> float:
        """
        Calculate institutional quality score (0-100).
        
        Args:
            avg_dollar_volume: Average daily dollar volume
            float_shares: Float shares
            volatility_profile: Volatility profile
            market_cap: Market cap
            
        Returns:
            Institutional quality score (0-100)
        """
        score = 50.0  # Base score
        
        # Dollar volume component (0-25 points)
        if avg_dollar_volume:
            if avg_dollar_volume >= 100_000_000:  # $100M/day
                score += 25
            elif avg_dollar_volume >= 10_000_000:  # $10M/day
                score += 20
            elif avg_dollar_volume >= 1_000_000:  # $1M/day
                score += 15
            elif avg_dollar_volume >= 500_000:  # $500K/day
                score += 10
            else:
                score += 5
        
        # Float component (0-15 points)
        if float_shares:
            float_value = float_shares * 100  # Approximate value
            if float_value >= 1_000_000_000:  # $1B
                score += 15
            elif float_value >= 500_000_000:  # $500M
                score += 12
            elif float_value >= 100_000_000:  # $100M
                score += 8
            else:
                score += 3
        
        # Volatility component (0-10 points)
        if volatility_profile:
            if volatility_profile == VolatilityProfile.LOW:
                score += 10
            elif volatility_profile == VolatilityProfile.MODERATE:
                score += 7
            elif volatility_profile == VolatilityProfile.HIGH:
                score += 3
            else:  # EXTREME
                score -= 5
        
        # Market cap component (0-10 points)
        if market_cap:
            if market_cap >= 10_000_000_000:  # $10B
                score += 10
            elif market_cap >= 2_000_000_000:  # $2B
                score += 7
            elif market_cap >= 500_000_000:  # $500M
                score += 4
            else:
                score += 1
        
        # Clamp to 0-100
        return max(0, min(100, score))
    
    def _calculate_tradability(
        self,
        avg_dollar_volume: Optional[float],
        atr_percent: Optional[float],
        current_price: Optional[float]
    ) -> float:
        """
        Calculate tradability score (0-100).
        
        Args:
            avg_dollar_volume: Average daily dollar volume
            atr_percent: ATR as percentage of price
            current_price: Current price
            
        Returns:
            Tradability score (0-100)
        """
        score = 50.0  # Base score
        
        # Dollar volume component (0-30 points)
        if avg_dollar_volume:
            if avg_dollar_volume >= 50_000_000:  # $50M/day
                score += 30
            elif avg_dollar_volume >= 10_000_000:  # $10M/day
                score += 25
            elif avg_dollar_volume >= 1_000_000:  # $1M/day
                score += 15
            else:
                score += 5
        
        # Volatility component (0-20 points)
        if atr_percent:
            if atr_percent < 2:
                score += 20
            elif atr_percent < 5:
                score += 15
            elif atr_percent < 10:
                score += 8
            else:
                score -= 5
        
        # Price component (0-10 points)
        if current_price:
            if 10 <= current_price <= 200:
                score += 10
            elif 5 <= current_price < 10 or 200 < current_price <= 500:
                score += 5
            else:
                score -= 5
        
        # Clamp to 0-100
        return max(0, min(100, score))
    
    def get_enrichment_statistics(self, enriched_tickers: List[EnrichedTicker]) -> Dict[str, Any]:
        """
        Get enrichment statistics.
        
        Args:
            enriched_tickers: List of enriched tickers
            
        Returns:
            Dictionary with statistics
        """
        total = len(enriched_tickers)
        
        if total == 0:
            return {"total": 0}
        
        # Calculate averages
        avg_dollar_volume = statistics.mean([t.avg_dollar_volume_20d for t in enriched_tickers if t.avg_dollar_volume_20d]) if any(t.avg_dollar_volume_20d for t in enriched_tickers) else None
        avg_institutional_quality = statistics.mean([t.institutional_quality_score for t in enriched_tickers if t.institutional_quality_score]) if any(t.institutional_quality_score for t in enriched_tickers) else None
        avg_tradability = statistics.mean([t.tradability_score for t in enriched_tickers if t.tradability_score]) if any(t.tradability_score for t in enriched_tickers) else None
        
        # Count by volatility profile
        volatility_counts = {}
        for ticker in enriched_tickers:
            if ticker.volatility_profile:
                volatility_counts[ticker.volatility_profile.value] = volatility_counts.get(ticker.volatility_profile.value, 0) + 1
        
        # Count by market cap tier
        tier_counts = {}
        for ticker in enriched_tickers:
            if ticker.market_cap_tier:
                tier_counts[ticker.market_cap_tier] = tier_counts.get(ticker.market_cap_tier, 0) + 1
        
        return {
            "total": total,
            "avg_dollar_volume": avg_dollar_volume,
            "avg_institutional_quality": avg_institutional_quality,
            "avg_tradability": avg_tradability,
            "volatility_distribution": volatility_counts,
            "market_cap_tier_distribution": tier_counts
        }
