import pandas as pd
import numpy as np
from typing import List, Tuple


def calculate_rs_rank(
    stock_rs: float,
    all_rs_values: List[float]
) -> float:
    """Calculate percentile rank of relative strength"""
    if not all_rs_values:
        return 50.0
    return (np.searchsorted(sorted(all_rs_values), stock_rs) / len(all_rs_values)) * 100


def calculate_rs_momentum(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    period: int = 20
) -> float:
    """Calculate momentum of relative strength over period"""
    if len(stock_prices) < period or len(benchmark_prices) < period:
        return 0.0
    
    stock_rs_current = stock_prices.iloc[-1] / benchmark_prices.iloc[-1]
    stock_rs_past = stock_prices.iloc[-period] / benchmark_prices.iloc[-period]
    
    if stock_rs_past == 0:
        return 0.0
    
    return ((stock_rs_current - stock_rs_past) / stock_rs_past) * 100


def detect_early_leader(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    short_period: int = 5,
    long_period: int = 20
) -> bool:
    """Detect if stock is showing early leadership signals"""
    if len(stock_prices) < long_period:
        return False
    
    # Calculate short-term and long-term RS
    short_rs = calculate_rs_momentum(stock_prices, benchmark_prices, short_period)
    long_rs = calculate_rs_momentum(stock_prices, benchmark_prices, long_period)
    
    # Leader if short-term momentum > long-term momentum and both positive
    return short_rs > long_rs and short_rs > 0
