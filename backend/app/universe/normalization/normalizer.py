"""
Universe Normalization Layer

Normalize data from all sources:
- Symbol standardization
- Canonical symbol resolution
- Exchange normalization
- Asset type classification
- Market cap normalization
- Sector/industry normalization
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, replace
import re

from app.universe.sources.universe_source import TickerInfo

logger = logging.getLogger(__name__)


class ExchangeNormalizer:
    """Normalize exchange codes"""
    
    EXCHANGE_MAPPING = {
        "XNYS": "NYSE",
        "XNAS": "NASDAQ",
        "XASE": "AMEX",
        "ARCX": "NYSE ARCA",
        "XNMS": "NASDAQ",
        "XNGS": "NASDAQ",
        "XCHI": "CHICAGO",
        "XPHL": "PHILADELPHIA",
        "XBOS": "BOSTON",
        "NASDAQ": "NASDAQ",
        "NYSE": "NYSE",
        "AMEX": "AMEX",
        "NYSE ARCA": "NYSE ARCA",
        "CHICAGO": "CHICAGO",
        "PHILADELPHIA": "PHILADELPHIA",
        "BOSTON": "BOSTON",
    }
    
    @classmethod
    def normalize(cls, exchange: str) -> str:
        """Normalize exchange code"""
        if not exchange:
            return "UNKNOWN"
        
        exchange_upper = exchange.upper()
        return cls.EXCHANGE_MAPPING.get(exchange_upper, exchange_upper)


class AssetTypeNormalizer:
    """Normalize asset type classification"""
    
    @classmethod
    def classify(cls, ticker_info: TickerInfo) -> str:
        """Classify asset type from ticker info"""
        # Check explicit asset type
        if ticker_info.asset_type:
            return cls._normalize_asset_type(ticker_info.asset_type)
        
        # Infer from symbol
        symbol = ticker_info.symbol.upper()
        
        # ETF indicators
        if symbol.endswith(("ETF", "ETN", "ETV", "ETN")):
            return "etf"
        
        # ADR indicators
        if symbol.endswith(("Y", "F")) and len(symbol) == 5:
            # Many ADRs end in Y or F
            return "adr"
        
        # Preferred stock indicators
        if "-" in symbol or symbol.endswith(("P", "PR")):
            return "preferred"
        
        # REIT indicators
        if ticker_info.name and ("REIT" in ticker_info.name.upper() or "REAL ESTATE" in ticker_info.name.upper()):
            return "reit"
        
        # Default to common stock
        return "common_stock"
    
    @classmethod
    def _normalize_asset_type(cls, asset_type: str) -> str:
        """Normalize asset type string"""
        asset_type_lower = asset_type.lower()
        
        if "etf" in asset_type_lower or "etn" in asset_type_lower:
            return "etf"
        elif "adr" in asset_type_lower:
            return "adr"
        elif "preferred" in asset_type_lower or "pref" in asset_type_lower:
            return "preferred"
        elif "reit" in asset_type_lower or "real estate" in asset_type_lower:
            return "reit"
        elif "warrant" in asset_type_lower:
            return "warrant"
        elif "common" in asset_type_lower:
            return "common_stock"
        else:
            return "common_stock"  # Default


class SymbolNormalizer:
    """Normalize ticker symbols"""
    
    @classmethod
    def normalize(cls, symbol: str) -> str:
        """Normalize symbol"""
        if not symbol:
            return ""
        
        # Remove whitespace
        symbol = symbol.strip()
        
        # Convert to uppercase
        symbol = symbol.upper()
        
        # Remove suffixes for canonical symbol
        # (e.g., BRK.B -> BRK, BRK.A -> BRK)
        if "." in symbol:
            symbol = symbol.split(".")[0]
        
        # Remove exchange suffixes
        # (e.g., AAPL-US -> AAPL)
        if "-" in symbol:
            symbol = symbol.split("-")[0]
        
        return symbol
    
    @classmethod
    def get_canonical(cls, symbol: str, historical_symbols: Optional[List[str]] = None) -> str:
        """
        Get canonical symbol, considering historical symbols.
        
        Args:
            symbol: Symbol to canonicalize
            historical_symbols: List of historical symbols for this instrument
            
        Returns:
            Canonical symbol
        """
        # Normalize the symbol
        normalized = cls.normalize(symbol)
        
        # If we have historical symbols, check if this is a historical symbol
        if historical_symbols:
            # Return the most recent symbol (last in list)
            if normalized in historical_symbols:
                # Find the most recent symbol that's not this one
                for hist_symbol in reversed(historical_symbols):
                    if hist_symbol != normalized:
                        return cls.normalize(hist_symbol)
        
        return normalized


class SectorNormalizer:
    """Normalize sector classifications"""
    
    SECTOR_MAPPING = {
        # GICS sectors
        "TECHNOLOGY": "Technology",
        "TECH": "Technology",
        "INFORMATION TECHNOLOGY": "Technology",
        "IT": "Technology",
        
        "HEALTHCARE": "Health Care",
        "HEALTH CARE": "Health Care",
        "HEALTH": "Health Care",
        
        "FINANCIALS": "Financials",
        "FINANCE": "Financials",
        "FINANCIAL": "Financials",
        "BANKING": "Financials",
        
        "CONSUMER DISCRETIONARY": "Consumer Discretionary",
        "CONSUMER CYCLICAL": "Consumer Discretionary",
        
        "CONSUMER STAPLES": "Consumer Staples",
        "CONSUMER NON-CYCLICAL": "Consumer Staples",
        
        "ENERGY": "Energy",
        "OIL & GAS": "Energy",
        
        "INDUSTRIALS": "Industrials",
        "INDUSTRIAL": "Industrials",
        
        "MATERIALS": "Materials",
        "BASIC MATERIALS": "Materials",
        
        "UTILITIES": "Utilities",
        "UTILITY": "Utilities",
        
        "REAL ESTATE": "Real Estate",
        "REIT": "Real Estate",
        
        "COMMUNICATION SERVICES": "Communication Services",
        "TELECOMMUNICATION": "Communication Services",
        "TELECOM": "Communication Services",
    }
    
    @classmethod
    def normalize(cls, sector: Optional[str]) -> Optional[str]:
        """Normalize sector name"""
        if not sector:
            return None
        
        sector_upper = sector.upper()
        return cls.SECTOR_MAPPING.get(sector_upper, sector)


class MarketCapNormalizer:
    """Normalize market cap values"""
    
    @classmethod
    def normalize(cls, market_cap: Optional[float]) -> Optional[float]:
        """Normalize market cap to float in USD"""
        if market_cap is None:
            return None
        
        if isinstance(market_cap, (int, float)):
            return float(market_cap)
        
        # Handle string formats like "1.2B", "500M", "2.5T"
        if isinstance(market_cap, str):
            market_cap = market_cap.upper()
            
            multiplier = 1
            if "T" in market_cap:
                multiplier = 1e12
                market_cap = market_cap.replace("T", "")
            elif "B" in market_cap:
                multiplier = 1e9
                market_cap = market_cap.replace("B", "")
            elif "M" in market_cap:
                multiplier = 1e6
                market_cap = market_cap.replace("M", "")
            
            try:
                return float(market_cap) * multiplier
            except ValueError:
                return None
        
        return None
    
    @classmethod
    def get_tier(cls, market_cap: Optional[float]) -> str:
        """Get market cap tier"""
        if market_cap is None:
            return "UNKNOWN"
        
        if market_cap >= 200e9:  # $200B+
            return "MEGA"
        elif market_cap >= 10e9:  # $10B+
            return "LARGE"
        elif market_cap >= 2e9:  # $2B+
            return "MID"
        elif market_cap >= 500e6:  # $500M+
            return "SMALL"
        else:
            return "MICRO"


class UniverseNormalizer:
    """
    Universe Normalizer
    
    Normalizes data from all sources:
    - Symbol standardization
    - Exchange normalization
    - Asset type classification
    - Market cap normalization
    - Sector/industry normalization
    """
    
    def __init__(self):
        self.exchange_normalizer = ExchangeNormalizer()
        self.asset_type_normalizer = AssetTypeNormalizer()
        self.symbol_normalizer = SymbolNormalizer()
        self.sector_normalizer = SectorNormalizer()
        self.market_cap_normalizer = MarketCapNormalizer()
    
    def normalize_ticker(self, ticker_info: TickerInfo) -> TickerInfo:
        """
        Normalize ticker information.
        
        Args:
            ticker_info: Raw ticker information
            
        Returns:
            Normalized TickerInfo
        """
        # Normalize symbol
        normalized_symbol = self.symbol_normalizer.normalize(ticker_info.symbol)
        
        # Normalize exchange
        normalized_exchange = self.exchange_normalizer.normalize(ticker_info.exchange)
        
        # Classify asset type
        normalized_asset_type = self.asset_type_normalizer.classify(ticker_info)
        
        # Normalize market cap
        normalized_market_cap = self.market_cap_normalizer.normalize(ticker_info.market_cap)
        
        # Normalize sector
        normalized_sector = self.sector_normalizer.normalize(ticker_info.sector)
        
        # Create normalized ticker
        normalized_ticker = replace(
            ticker_info,
            symbol=normalized_symbol,
            exchange=normalized_exchange,
            asset_type=normalized_asset_type,
            market_cap=normalized_market_cap,
            sector=normalized_sector
        )
        
        return normalized_ticker
    
    def normalize_tickers(self, tickers: List[TickerInfo]) -> List[TickerInfo]:
        """
        Normalize multiple tickers.
        
        Args:
            tickers: List of raw ticker information
            
        Returns:
            List of normalized TickerInfo
        """
        normalized = []
        seen_symbols = set()
        
        for ticker in tickers:
            normalized_ticker = self.normalize_ticker(ticker)
            
            # Deduplicate by symbol
            if normalized_ticker.symbol not in seen_symbols:
                seen_symbols.add(normalized_ticker.symbol)
                normalized.append(normalized_ticker)
        
        logger.info(f"Normalized {len(normalized)} tickers (deduped from {len(tickers)})")
        return normalized
    
    def deduplicate_by_symbol(self, tickers: List[TickerInfo]) -> List[TickerInfo]:
        """
        Deduplicate tickers by symbol, keeping the most complete record.
        
        Args:
            tickers: List of ticker information
            
        Returns:
            Deduplicated list
        """
        symbol_map: Dict[str, TickerInfo] = {}
        
        for ticker in tickers:
            symbol = ticker.symbol
            if symbol not in symbol_map:
                symbol_map[symbol] = ticker
            else:
                # Keep the one with more complete data
                existing = symbol_map[symbol]
                if self._is_more_complete(ticker, existing):
                    symbol_map[symbol] = ticker
        
        return list(symbol_map.values())
    
    def _is_more_complete(self, ticker1: TickerInfo, ticker2: TickerInfo) -> bool:
        """Check if ticker1 has more complete data than ticker2"""
        fields1 = sum(1 for field in [ticker1.name, ticker1.sector, ticker1.industry, ticker1.market_cap] if field)
        fields2 = sum(1 for field in [ticker2.name, ticker2.sector, ticker2.industry, ticker2.market_cap] if field)
        
        return fields1 > fields2
    
    def get_normalization_statistics(self, original: List[TickerInfo], normalized: List[TickerInfo]) -> Dict[str, Any]:
        """
        Get normalization statistics.
        
        Args:
            original: Original tickers
            normalized: Normalized tickers
            
        Returns:
            Dictionary with statistics
        """
        return {
            "original_count": len(original),
            "normalized_count": len(normalized),
            "deduplicated_count": len(original) - len(normalized),
            "symbols_normalized": len(normalized),
            "exchanges_normalized": len(set(t.exchange for t in normalized)),
            "asset_types": len(set(t.asset_type for t in normalized)),
            "sectors": len(set(t.sector for t in normalized if t.sector))
        }
