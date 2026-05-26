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
    stock_return_pct: float,
    benchmark_return_pct: float,
) -> float:
    """Calculate relative strength (Mansfield-style, normalized to 100).

    RS = ((1 + stock_return) / (1 + benchmark_return)) * 100

    100 = parity, >100 = outperforming benchmark, <100 = underperforming.
    Inputs are percentage returns over the same period (e.g., 13w).
    """
    stock_factor = 1.0 + (stock_return_pct / 100.0)
    benchmark_factor = 1.0 + (benchmark_return_pct / 100.0)
    if benchmark_factor <= 0:
        return 100.0
    return float((stock_factor / benchmark_factor) * 100.0)


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


def calculate_adr_percent(df: pd.DataFrame, days: int = 20) -> float:
    """Average Daily Range as percentage of close price.

    Standard formula: mean((high - low) / close * 100) over last N days.
    Stocks with insufficient valid data return 0.0.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("calculate_adr_percent expects DataFrame with high/low/close columns")
    required = {'high', 'low', 'close'}
    if not required.issubset(df.columns):
        raise TypeError(f"DataFrame must contain columns: {required}")

    recent = df.tail(days).dropna(subset=['high', 'low', 'close'])
    valid = recent[recent['close'] > 0]
    if len(valid) < 5:
        return 0.0

    daily_range_pct = (valid['high'] - valid['low']) / valid['close'] * 100
    return float(daily_range_pct.mean())


def _find_pivots(series: pd.Series, left: int = 3, right: int = 3, kind: str = 'high') -> list:
    pivots = []
    for i in range(left, len(series) - right):
        window_left = series.iloc[i-left:i]
        window_right = series.iloc[i+1:i+1+right]
        if kind == 'high':
            if series.iloc[i] >= window_left.max() and series.iloc[i] >= window_right.max():
                pivots.append((i, float(series.iloc[i])))
        else:
            if series.iloc[i] <= window_left.min() and series.iloc[i] <= window_right.min():
                pivots.append((i, float(series.iloc[i])))
    return pivots


def _build_contractions(pivots_high: list, pivots_low: list) -> list:
    contractions = []
    hi, li = 0, 0
    while hi < len(pivots_high) and li < len(pivots_low):
        h_pos, h_val = pivots_high[hi]
        l_pos, l_val = pivots_low[li]
        if l_pos > h_pos:
            depth = (h_val - l_val) / h_val * 100 if h_val > 0 else 0.0
            if depth > 0:
                contractions.append({'high_idx': h_pos, 'low_idx': l_pos, 'depth_pct': depth})
            hi += 1
            li += 1
        else:
            li += 1
    return contractions


def detect_vcp(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Detect VCP pattern on daily timeframe.
    Returns: {'score': float, 'count': int, 'latest_depth_pct': float|None}
    """
    result = {'score': 0.0, 'count': 0, 'latest_depth_pct': None}
    if not isinstance(df, pd.DataFrame) or len(df) < 15:
        return result
    if not {'high', 'low', 'volume'}.issubset(df.columns):
        return result

    recent = df.tail(lookback).reset_index(drop=True)
    pivots_high = _find_pivots(recent['high'], 3, 3, 'high')
    pivots_low = _find_pivots(recent['low'], 3, 3, 'low')
    contractions = _build_contractions(pivots_high, pivots_low)

    if len(contractions) < 2:
        return result

    count_score = min(40, len(contractions) * 15)
    narrowing_pairs = sum(
        1 for i in range(len(contractions) - 1)
        if contractions[i]['depth_pct'] > contractions[i+1]['depth_pct']
    )
    narrowing_score = (narrowing_pairs / max(1, len(contractions) - 1)) * 40

    half = lookback // 2
    vol_first = recent['volume'].iloc[:half].mean()
    vol_second = recent['volume'].iloc[half:].mean()
    vol_ratio = vol_second / vol_first if vol_first > 0 else 1.0
    vol_score = max(0, min(20, (1 - vol_ratio) * 40))

    total = count_score + narrowing_score + vol_score
    result['score'] = round(total, 1)
    result['count'] = len(contractions)
    result['latest_depth_pct'] = round(contractions[-1]['depth_pct'], 2)
    return result


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
