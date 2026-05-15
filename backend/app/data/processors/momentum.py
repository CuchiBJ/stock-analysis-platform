import pandas as pd
import numpy as np
from typing import Optional


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return prices.ewm(span=period, adjust=False).mean()


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return prices.rolling(window=period).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_relative_strength(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series
) -> float:
    """Calculate relative strength ratio (stock / benchmark)"""
    if len(stock_prices) != len(benchmark_prices):
        min_len = min(len(stock_prices), len(benchmark_prices))
        stock_prices = stock_prices[-min_len:]
        benchmark_prices = benchmark_prices[-min_len:]
    
    return float((stock_prices.iloc[-1] / benchmark_prices.iloc[-1]) * 100)


def calculate_distance_to_ema(current_price: float, ema: float) -> float:
    """Calculate percentage distance to EMA"""
    if ema == 0:
        return 0.0
    return ((current_price - ema) / ema) * 100


def calculate_relative_volume(current_volume: int, avg_volume: float) -> float:
    """Calculate relative volume ratio"""
    if avg_volume == 0:
        return 0.0
    return current_volume / avg_volume


def calculate_performance(prices: pd.Series, days: int) -> float:
    """Calculate percentage performance over N days"""
    if len(prices) < 2:
        return 0.0
    # Use available data if not enough for full period
    available_days = min(len(prices) - 1, days)
    if available_days < 1:
        return 0.0
    start_price = prices.iloc[-available_days-1]
    end_price = prices.iloc[-1]
    if start_price == 0:
        return 0.0
    return ((end_price - start_price) / start_price) * 100


def calculate_adr_percent(prices: pd.Series, days: int = 20) -> float:
    """Calculate Average Daily Range percentage over N days"""
    if len(prices) < days + 1:
        return 0.0
    
    recent_prices = prices.tail(days + 1)
    daily_changes = recent_prices.pct_change().abs()
    return daily_changes.mean() * 100


def detect_breakout(
    prices: pd.Series,
    lookback: int = 20,
    threshold: float = 0.02
) -> bool:
    """Detect if price broke above recent high"""
    if len(prices) < lookback + 1:
        return False
    
    recent_high = prices[-lookback-1:-1].max()
    current_price = prices.iloc[-1]
    
    return current_price > (recent_high * (1 + threshold))
