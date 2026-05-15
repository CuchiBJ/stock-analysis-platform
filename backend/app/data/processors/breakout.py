import pandas as pd
import numpy as np
from typing import Optional, Tuple


def detect_consolidation(
    prices: pd.Series,
    volume: pd.Series,
    lookback: int = 20,
    max_range_pct: float = 0.15
) -> Tuple[bool, Optional[float]]:
    """Detect if stock is in consolidation (tight range, low volatility)"""
    if len(prices) < lookback:
        return False, None
    
    recent_prices = prices[-lookback:]
    price_range = (recent_prices.max() - recent_prices.min()) / recent_prices.mean()
    
    is_consolidating = price_range <= max_range_pct
    return is_consolidating, price_range


def detect_squeeze(
    prices: pd.Series,
    lookback: int = 20
) -> bool:
    """Detect Bollinger Band squeeze (low volatility before expansion)"""
    if len(prices) < lookback:
        return False
    
    recent = prices[-lookback:]
    std = recent.std()
    mean = recent.mean()
    
    # Check if recent volatility is lower than historical average
    if len(prices) > lookback * 2:
        historical_std = prices[-lookback*2:-lookback].std()
        return std < historical_std * 0.7
    
    return False


def detect_gap_up(
    open_price: float,
    previous_close: float,
    threshold: float = 0.02
) -> bool:
    """Detect gap up opening"""
    if previous_close == 0:
        return False
    gap_pct = (open_price - previous_close) / previous_close
    return gap_pct >= threshold


def detect_near_high(
    current_price: float,
    high_52w: float,
    threshold: float = 0.05
) -> bool:
    """Check if price is within threshold of 52-week high"""
    if high_52w == 0:
        return False
    distance = (high_52w - current_price) / high_52w
    return distance <= threshold
