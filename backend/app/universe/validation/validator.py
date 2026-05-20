"""
Universe Validation Layer

Quality filters to remove garbage:
- Liquidity filter
- Price filter
- Float filter
- Volatility filter
- Tradability filter
- Exchange filter
- Asset type filter
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, replace
from enum import Enum

from app.universe.sources.universe_source import TickerInfo

logger = logging.getLogger(__name__)


class ValidationRule(Enum):
    """Validation rule types"""
    EXCHANGE = "exchange"
    ASSET_TYPE = "asset_type"
    LIQUIDITY = "liquidity"
    PRICE = "price"
    FLOAT = "float"
    VOLATILITY = "volatility"
    TRADABILITY = "tradability"


@dataclass
class ValidationConfig:
    """Validation configuration"""
    # Exchange filter
    allowed_exchanges: List[str] = None
    # Asset type filter
    allowed_asset_types: List[str] = None
    excluded_asset_types: List[str] = None
    # Liquidity filter
    min_avg_volume: int = 500000  # 500K shares/day
    min_avg_dollar_volume: float = 1000000  # $1M/day
    # Price filter
    min_price: float = 5.0  # $5 minimum
    max_price: float = 1000.0  # $1000 maximum
    # Float filter
    min_float: float = 50000000  # $50M minimum
    # Volatility filter
    max_atr_percent: float = 20.0  # 20% ATR max
    # Tradability filter
    max_spread_percent: float = 1.0  # 1% spread max


@dataclass
class ValidationResult:
    """Result of validation"""
    passed: bool
    ticker_info: TickerInfo
    failed_rules: List[ValidationRule]
    reasons: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "passed": self.passed,
            "symbol": self.ticker_info.symbol,
            "failed_rules": [rule.value for rule in self.failed_rules],
            "reasons": self.reasons
        }


class UniverseValidator:
    """
    Universe Validator
    
    Quality filters to remove garbage:
    - Exchange filter (only major exchanges)
    - Asset type filter (exclude ETFs, warrants, preferreds)
    - Liquidity filter (min volume, min dollar volume)
    - Price filter (avoid penny stocks)
    - Float filter (min float size)
    - Volatility filter (avoid hyper-volatile garbage)
    - Tradability filter (spread, depth)
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        
        # Default allowed exchanges (major US exchanges)
        if not self.config.allowed_exchanges:
            self.config.allowed_exchanges = [
                "NASDAQ",
                "NYSE",
                "AMEX",
                "NYSE ARCA"
            ]
        
        # Default allowed asset types (for setup analysis)
        if not self.config.allowed_asset_types:
            self.config.allowed_asset_types = ["common_stock"]
        
        # Default excluded asset types
        if not self.config.excluded_asset_types:
            self.config.excluded_asset_types = [
                "etf",
                "warrant",
                "preferred",
                "unit"
            ]
    
    def validate(self, ticker_info: TickerInfo, price_data: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate ticker against quality rules.
        
        Args:
            ticker_info: Ticker information
            price_data: Optional price data for advanced validation
            
        Returns:
            ValidationResult
        """
        failed_rules = []
        reasons = []
        
        # Exchange validation
        if not self._validate_exchange(ticker_info):
            failed_rules.append(ValidationRule.EXCHANGE)
            reasons.append(f"Exchange {ticker_info.exchange} not in allowed list")
        
        # Asset type validation
        if not self._validate_asset_type(ticker_info):
            failed_rules.append(ValidationRule.ASSET_TYPE)
            reasons.append(f"Asset type {ticker_info.asset_type} excluded")
        
        # Price validation (if price data available)
        if price_data:
            current_price = price_data.get("close")
            if not self._validate_price(current_price):
                failed_rules.append(ValidationRule.PRICE)
                reasons.append(f"Price {current_price} outside valid range")
            
            # Liquidity validation (if volume data available)
            avg_volume = price_data.get("avg_volume")
            if not self._validate_liquidity(avg_volume, current_price):
                failed_rules.append(ValidationRule.LIQUIDITY)
                reasons.append(f"Insufficient liquidity (volume: {avg_volume})")
            
            # Volatility validation (if ATR data available)
            atr = price_data.get("atr")
            if not self._validate_volatility(atr, current_price):
                failed_rules.append(ValidationRule.VOLATILITY)
                reasons.append(f"Volatility too high (ATR: {atr})")
            
            # Float validation (if float data available)
            float_shares = price_data.get("float_shares")
            if not self._validate_float(float_shares, current_price):
                failed_rules.append(ValidationRule.FLOAT)
                reasons.append(f"Insufficient float (shares: {float_shares})")
            
            # Tradability validation (if spread data available)
            spread = price_data.get("spread")
            if not self._validate_tradability(spread, current_price):
                failed_rules.append(ValidationRule.TRADABILITY)
                reasons.append(f"Poor tradability (spread: {spread})")
        
        passed = len(failed_rules) == 0
        
        return ValidationResult(
            passed=passed,
            ticker_info=ticker_info,
            failed_rules=failed_rules,
            reasons=reasons
        )
    
    def validate_batch(self, tickers: List[TickerInfo], price_data_map: Optional[Dict[str, Dict[str, Any]]] = None) -> List[ValidationResult]:
        """
        Validate multiple tickers.
        
        Args:
            tickers: List of ticker information
            price_data_map: Optional mapping of symbol to price data
            
        Returns:
            List of ValidationResult
        """
        results = []
        
        for ticker in tickers:
            price_data = price_data_map.get(ticker.symbol) if price_data_map else None
            result = self.validate(ticker, price_data)
            results.append(result)
        
        passed_count = sum(1 for r in results if r.passed)
        logger.info(f"Validation: {passed_count}/{len(results)} tickers passed")
        
        return results
    
    def filter_valid(self, tickers: List[TickerInfo], price_data_map: Optional[Dict[str, Dict[str, Any]]] = None) -> List[TickerInfo]:
        """
        Filter to only valid tickers.
        
        Args:
            tickers: List of ticker information
            price_data_map: Optional mapping of symbol to price data
            
        Returns:
            List of valid tickers
        """
        results = self.validate_batch(tickers, price_data_map)
        valid_tickers = [r.ticker_info for r in results if r.passed]
        
        logger.info(f"Filtered to {len(valid_tickers)} valid tickers from {len(tickers)}")
        return valid_tickers
    
    def _validate_exchange(self, ticker_info: TickerInfo) -> bool:
        """Validate exchange"""
        if not ticker_info.exchange:
            return False
        
        return ticker_info.exchange in self.config.allowed_exchanges
    
    def _validate_asset_type(self, ticker_info: TickerInfo) -> bool:
        """Validate asset type"""
        asset_type = ticker_info.asset_type.lower() if ticker_info.asset_type else ""
        
        # Check if in excluded list
        if asset_type in [t.lower() for t in self.config.excluded_asset_types]:
            return False
        
        # Check if in allowed list
        if self.config.allowed_asset_types:
            return asset_type in [t.lower() for t in self.config.allowed_asset_types]
        
        return True
    
    def _validate_price(self, price: Optional[float]) -> bool:
        """Validate price range"""
        if price is None:
            return True  # Skip validation if no price data
        
        return self.config.min_price <= price <= self.config.max_price
    
    def _validate_liquidity(self, volume: Optional[int], price: Optional[float]) -> bool:
        """Validate liquidity"""
        if volume is None:
            return True  # Skip validation if no volume data
        
        # Check share volume
        if volume < self.config.min_avg_volume:
            return False
        
        # Check dollar volume if price available
        if price and volume * price < self.config.min_avg_dollar_volume:
            return False
        
        return True
    
    def _validate_float(self, float_shares: Optional[int], price: Optional[float]) -> bool:
        """Validate float size"""
        if float_shares is None or price is None:
            return True  # Skip validation if no float data
        
        float_value = float_shares * price
        return float_value >= self.config.min_float
    
    def _validate_volatility(self, atr: Optional[float], price: Optional[float]) -> bool:
        """Validate volatility"""
        if atr is None or price is None:
            return True  # Skip validation if no ATR data
        
        atr_percent = (atr / price) * 100
        return atr_percent <= self.config.max_atr_percent
    
    def _validate_tradability(self, spread: Optional[float], price: Optional[float]) -> bool:
        """Validate tradability"""
        if spread is None or price is None:
            return True  # Skip validation if no spread data
        
        spread_percent = (spread / price) * 100
        return spread_percent <= self.config.max_spread_percent
    
    def get_validation_statistics(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Get validation statistics.
        
        Args:
            results: List of validation results
            
        Returns:
            Dictionary with statistics
        """
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        
        # Count failures by rule
        rule_failures: Dict[str, int] = {}
        for result in results:
            for rule in result.failed_rules:
                rule_failures[rule.value] = rule_failures.get(rule.value, 0) + 1
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0,
            "rule_failures": rule_failures
        }
    
    def update_config(self, **kwargs):
        """
        Update validation configuration.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"Updated validation config: {kwargs}")
